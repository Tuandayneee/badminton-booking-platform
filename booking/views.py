from collections import defaultdict
from datetime import datetime as dt, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import redis
import requests

from partner.models import BadmintonCenter, Court, Customer
from .models import Booking, Transaction

logger = logging.getLogger(__name__)

_redis_pool = None


def get_redis():
    """Return a Redis client backed by a shared connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return redis.Redis(connection_pool=_redis_pool)


def build_internal_lock_token(user_id):
    """Create a short-lived HMAC-SHA256 token for authenticating to FastAPI lock API."""
    secret = settings.INTERNAL_LOCK_SECRET
    ts = str(int(time.time()))
    payload = f"{ts}:{user_id}".encode('utf-8')
    sig = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    return f"{ts}:{user_id}:{sig}"


def _release_redis_locks(lock_keys):
    if not lock_keys:
        return
    try:
        get_redis().delete(*lock_keys)
    except redis.RedisError as exc:
        logger.warning("Failed to release Redis locks %s: %s", lock_keys, exc)


@login_required
@require_POST
def proxy_lock_slot(request):
    """Proxy slot-lock requests through Django using the authenticated session user."""
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'detail': 'Dữ liệu JSON không hợp lệ'}, status=400)

    court_id = body.get('court_id')
    date_str = body.get('date')
    start_time_str = body.get('start_time')
    end_time_str = body.get('end_time') or start_time_str

    if not court_id or not date_str or not start_time_str:
        return JsonResponse({'detail': 'Thiếu thông tin sân hoặc khung giờ'}, status=400)

    try:
        booking_date = dt.strptime(date_str, "%Y-%m-%d").date()
        start_time_obj = dt.strptime(start_time_str, "%H:%M").time()
    except ValueError:
        return JsonResponse({'detail': 'Định dạng ngày hoặc giờ không hợp lệ'}, status=400)

    now_local = timezone.localtime()
    today = now_local.date()
    if booking_date < today or (booking_date == today and start_time_obj <= now_local.time()):
        return JsonResponse({'detail': 'Không thể giữ chỗ cho khung giờ trong quá khứ'}, status=400)

    if not Court.objects.filter(id=court_id, is_active=True, center__is_active=True).exists():
        return JsonResponse({'detail': 'Sân không tồn tại hoặc đang ngừng hoạt động'}, status=404)

    token = build_internal_lock_token(request.user.id)
    try:
        resp = requests.post(
            f"{settings.FASTAPI_INTERNAL_URL}/api/v1/lock-slot/",
            json={
                'court_id': court_id,
                'date': date_str,
                'start_time': start_time_str,
                'end_time': end_time_str,
            },
            headers={'X-Internal-Token': token},
            timeout=5,
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {'detail': 'Phản hồi không hợp lệ từ dịch vụ giữ chỗ'}
        return JsonResponse(payload, status=resp.status_code)
    except requests.RequestException as exc:
        logger.error("Failed to call FastAPI lock service: %s", exc)
        return JsonResponse(
            {'detail': 'Không thể kết nối dịch vụ giữ chỗ. Vui lòng thử lại.'},
            status=503,
        )


@login_required
def booking_timeline(request, center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id)
    courts = list(Court.objects.filter(center=center, is_active=True))

    now_local = timezone.localtime()
    today = now_local.date()
    end_of_year = today.replace(month=12, day=31)
    current_real_time = now_local.time()

    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            current_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()
            if current_date < today:
                current_date = today
        except ValueError:
            current_date = today
    else:
        current_date = today
    is_today = current_date == today

    booked_slots = Booking.objects.filter(
        court__center=center,
        date=current_date,
    ).exclude(status=Booking.Status.ADMIN_CANCELLED)

    bookings_by_court = defaultdict(list)
    for b in booked_slots:
        bookings_by_court[b.court_id].append(b)

    open_t = center.open_time or dt.strptime("05:00", "%H:%M").time()
    close_t = center.close_time or dt.strptime("22:00", "%H:%M").time()
    start_datetime = dt.combine(current_date, open_t)
    end_datetime = dt.combine(current_date, close_t)

    time_labels = []
    current = start_datetime
    while current <= end_datetime:
        time_labels.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)

    date_str = current_date.strftime('%Y-%m-%d')
    courts_data = []
    free_slot_refs = []

    for court in courts:
        slots_info = []
        court_bookings = bookings_by_court.get(court.id, [])

        for slot_idx, time_str in enumerate(time_labels):
            price = court.get_price_at_time(time_str)
            current_slot_time = dt.strptime(time_str, "%H:%M").time()

            if current_date < today or (is_today and current_slot_time <= current_real_time):
                status = 'expired'
            else:
                status = 'free'

            for booking in court_bookings:
                if booking.start_time <= current_slot_time < booking.end_time:
                    status = 'completed' if status == 'expired' else 'booked'
                    break

            if status == 'free':
                lock_key = f"lock:court_{court.id}_{date_str}_{time_str}"
                free_slot_refs.append((len(courts_data), slot_idx, lock_key))

            is_golden = (
                status == 'free'
                and court.golden_start_time is not None
                and court.golden_end_time is not None
                and court.golden_start_time <= current_slot_time < court.golden_end_time
            )

            slots_info.append({
                'time': time_str,
                'price': price,
                'is_golden': is_golden,
                'status': status,
            })

        courts_data.append({
            'court_obj': court,
            'slots': slots_info,
        })

    if free_slot_refs:
        try:
            lock_keys = [ref[2] for ref in free_slot_refs]
            lock_holders = get_redis().mget(lock_keys)
            current_user_id = str(request.user.id) if request.user.is_authenticated else None
            for (court_idx, slot_idx, _), holder in zip(free_slot_refs, lock_holders):
                if holder and holder.decode('utf-8') != current_user_id:
                    slot = courts_data[court_idx]['slots'][slot_idx]
                    slot['status'] = 'booked'
                    slot['is_golden'] = False
        except redis.RedisError as exc:
            logger.warning("Redis error while fetching court locks: %s", exc)

    context = {
        'center': center,
        'time_labels': time_labels,
        'courts_data': courts_data,
        'selected_date': date_str,
        'min_date': today.strftime('%Y-%m-%d'),
        'max_date': end_of_year.strftime('%Y-%m-%d'),
    }
    return render(request, 'booking/booking_timeline.html', context)


@login_required
@require_POST
def booking_confirm(request):
    booking_data_str = request.POST.get('booking_data', '[]')
    selected_date_str = request.POST.get('selected_date', '')
    center_id = request.POST.get('center_id')
    center = get_object_or_404(BadmintonCenter, pk=center_id)

    try:
        raw_items = json.loads(booking_data_str)
        selected_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("Danh sách khung giờ trống")
    except (ValueError, TypeError, json.JSONDecodeError):
        messages.error(request, "Dữ liệu đặt sân không hợp lệ.")
        return redirect('booking_timeline', center_id=center.id)

    now_local = timezone.localtime()
    today = now_local.date()
    if selected_date < today:
        messages.error(request, "Không thể đặt sân cho ngày trong quá khứ.")
        return redirect('booking_timeline', center_id=center.id)

    court_ids = {item.get('court_id') for item in raw_items if isinstance(item, dict)}
    courts_map = {
        str(c.id): c
        for c in Court.objects.filter(id__in=court_ids, center=center, is_active=True)
    }

    validated_items = []
    total_price = Decimal('0')
    for item in raw_items:
        if not isinstance(item, dict):
            messages.error(request, "Định dạng khung giờ không hợp lệ.")
            return redirect('booking_timeline', center_id=center.id)
        court = courts_map.get(str(item.get('court_id')))
        time_str = item.get('time', '')
        if not court:
            messages.error(request, "Sân được chọn không hợp lệ hoặc không thuộc trung tâm này.")
            return redirect('booking_timeline', center_id=center.id)
        try:
            slot_time = dt.strptime(time_str, "%H:%M").time()
        except ValueError:
            messages.error(request, f"Khung giờ '{time_str}' không hợp lệ.")
            return redirect('booking_timeline', center_id=center.id)

        if selected_date == today and slot_time <= now_local.time():
            messages.error(request, f"Khung giờ {time_str} đã qua, vui lòng chọn khung giờ khác.")
            return redirect('booking_timeline', center_id=center.id)

        server_price = (Decimal(court.get_price_at_time(time_str)) / Decimal('2')).quantize(Decimal('1'))
        total_price += server_price
        validated_items.append({
            'court_id': court.id,
            'court_name': court.name,
            'time': time_str,
            'price': int(server_price),
        })

    context = {
        'center': center,
        'booking_items': validated_items,
        'booking_data_json': json.dumps(validated_items),
        'selected_date': selected_date,
        'total_price': int(total_price),
    }
    return render(request, 'booking/booking_confirm.html', context)


@login_required
@require_POST
def booking_save(request):
    acquired_locks_to_rollback = []
    center_id = request.POST.get('center_id')
    center = get_object_or_404(BadmintonCenter, pk=center_id)

    try:
        booking_data_str = request.POST.get('booking_data', '[]')
        selected_date_str = request.POST.get('selected_date', '')

        full_name = request.POST.get('full_name') or request.user.full_name or request.user.username
        phone_number = request.POST.get('phone_number') or request.user.phone_number or ''
        email = request.user.email or ''
        note = request.POST.get('note', '')

        booking_items = json.loads(booking_data_str)
        booking_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()

        if not isinstance(booking_items, list) or not booking_items:
            messages.error(request, "Vui lòng chọn ít nhất một khung giờ.")
            return redirect('booking_timeline', center_id=center_id)

        now_local = timezone.localtime()
        today = now_local.date()
        if booking_date < today:
            messages.error(request, "Không thể đặt sân cho ngày trong quá khứ.")
            return redirect('booking_timeline', center_id=center_id)

        user_id = request.user.id
        date_str = booking_date.strftime('%Y-%m-%d')
        parsed_slots = []

        for item in booking_items:
            if not isinstance(item, dict) or 'court_id' not in item or 'time' not in item:
                messages.error(request, "Dữ liệu khung giờ không hợp lệ.")
                return redirect('booking_timeline', center_id=center_id)

            court_id = int(item['court_id'])
            start_time_str = item['time']
            start_time = dt.strptime(start_time_str, "%H:%M").time()
            if booking_date == today and start_time <= now_local.time():
                _release_redis_locks(acquired_locks_to_rollback)
                messages.error(request, f"Khung giờ {start_time_str} đã qua, không thể đặt.")
                return redirect('booking_timeline', center_id=center_id)

            lock_key = f"lock:court_{court_id}_{date_str}_{start_time_str}"
            holder_id = get_redis().get(lock_key)

            if holder_id:
                if int(holder_id) != user_id:
                    messages.error(request, f"Rất tiếc! Khung giờ {start_time_str} đã bị người khác nhanh tay đặt trước.")
                    return redirect('booking_timeline', center_id=center_id)
                acquired_locks_to_rollback.append(lock_key)
            else:
                _release_redis_locks(acquired_locks_to_rollback)
                messages.error(request, "Phiên đặt sân đã hết hạn hoặc chưa được giữ chỗ. Vui lòng chọn lại.")
                return redirect('booking_timeline', center_id=center_id)

            end_time = (dt.combine(booking_date, start_time) + timedelta(minutes=30)).time()
            parsed_slots.append((court_id, start_time_str, start_time, end_time))

        group_code = f"BK-{uuid.uuid4().hex[:8].upper()}"
        court_ids = sorted({slot[0] for slot in parsed_slots})

        with transaction.atomic():
            locked_courts = {
                c.id: c
                for c in Court.objects.select_for_update().filter(
                    id__in=court_ids,
                    center=center,
                    is_active=True,
                )
            }
            if len(locked_courts) != len(court_ids):
                _release_redis_locks(acquired_locks_to_rollback)
                messages.error(request, "Sân được chọn không tồn tại hoặc không thuộc trung tâm này.")
                return redirect('booking_timeline', center_id=center_id)

            for court_id, start_time_str, start_time, end_time in parsed_slots:
                existing_booking = Booking.objects.filter(
                    court_id=court_id,
                    date=booking_date,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                ).exclude(status=Booking.Status.ADMIN_CANCELLED).first()

                if existing_booking:
                    _release_redis_locks(acquired_locks_to_rollback)
                    messages.error(
                        request,
                        f"Rất tiếc! Khung giờ {start_time_str} đã có người đặt trước (Mã: {existing_booking.booking_code}).",
                    )
                    return redirect('booking_timeline', center_id=center_id)

            customer, created = Customer.objects.get_or_create(
                center=center,
                phone=phone_number,
                defaults={'name': full_name, 'email': email, 'user': request.user},
            )
            if not created:
                updated_fields = []
                if full_name and customer.name != full_name:
                    customer.name = full_name
                    updated_fields.append('name')
                if not customer.user:
                    customer.user = request.user
                    updated_fields.append('user')
                if updated_fields:
                    customer.save(update_fields=updated_fields)

            for idx, (court_id, start_time_str, start_time, end_time) in enumerate(parsed_slots, start=1):
                court = locked_courts[court_id]
                server_price = (Decimal(court.get_price_at_time(start_time_str)) / Decimal('2')).quantize(Decimal('1'))
                Booking.objects.create(
                    booking_code=f"{group_code}-{idx}",
                    group_code=group_code,
                    user=request.user,
                    court=court,
                    customer=customer,
                    date=booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    total_price=server_price,
                    status=Booking.Status.PENDING,
                    note=note,
                )

        _release_redis_locks(acquired_locks_to_rollback)
        messages.success(request, "Đã giữ sân thành công! Vui lòng thanh toán.")
        return redirect('booking_payment', group_code=group_code)

    except IntegrityError:
        _release_redis_locks(acquired_locks_to_rollback)
        messages.error(request, "Lỗi dữ liệu: Có xung đột lịch đặt sân.")
        return redirect('booking_timeline', center_id=center_id)

    except (ValueError, TypeError, json.JSONDecodeError, redis.RedisError) as exc:
        logger.warning("Booking save validation/redis error for center %s: %s", center_id, exc)
        _release_redis_locks(acquired_locks_to_rollback)
        messages.warning(request, "Có lỗi xảy ra, vui lòng thử lại.")
        return redirect('booking_timeline', center_id=center_id)

    except Exception:
        logger.exception("Unexpected error in booking_save for center %s", center_id)
        _release_redis_locks(acquired_locks_to_rollback)
        messages.warning(request, "Có lỗi xảy ra, vui lòng thử lại.")
        return redirect('booking_timeline', center_id=center_id)


@login_required
def booking_payment(request, group_code):
    bookings = Booking.objects.filter(group_code=group_code, user=request.user)

    if not bookings.exists():
        messages.error(request, "Đơn hàng không tồn tại!")
        return redirect('home')

    first_booking = bookings.first()
    if first_booking.status != Booking.Status.PENDING:
        messages.info(request, "Đơn hàng này không ở trạng thái chờ thanh toán.")
        return redirect('customer_booking_history')

    center = first_booking.court.center
    partner = center.partner
    total_price = sum(b.total_price for b in bookings)
    bank_id = partner.bank_bin
    account_no = partner.bank_account_number
    account_name = partner.bank_account_owner
    content = f"THANHTOAN {group_code}"
    qr_url = (
        f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png"
        f"?amount={int(total_price)}&addInfo={content}&accountName={account_name}"
    )

    timeout_minutes = 10
    expire_time = first_booking.created_at + timedelta(minutes=timeout_minutes)
    remaining_seconds = (expire_time - timezone.now()).total_seconds()
    if remaining_seconds <= 0:
        lock_keys = [
            f"lock:court_{b.court_id}_{b.date.strftime('%Y-%m-%d')}_{b.start_time.strftime('%H:%M')}"
            for b in bookings
        ]
        _release_redis_locks(lock_keys)
        bookings.update(status=Booking.Status.ADMIN_CANCELLED)
        messages.error(request, "Đơn hàng đã hết hạn thanh toán!")
        return redirect('home')

    context = {
        'bookings': bookings,
        'first_booking': first_booking,
        'total_price': total_price,
        'group_code': group_code,
        'qr_url': qr_url,
        'bank_info': {
            'bank_name': bank_id,
            'account_no': account_no,
            'account_name': account_name,
        },
        'time_left': int(remaining_seconds),
    }
    return render(request, 'booking/booking_payment.html', context)


@login_required
@require_POST
def booking_success_confirm(request, group_code):
    bookings = Booking.objects.filter(group_code=group_code, user=request.user)
    if not bookings.exists():
        messages.error(request, "Không tìm thấy đơn hàng!")
        return redirect('home')

    pending_bookings = bookings.filter(status=Booking.Status.PENDING)
    if not pending_bookings.exists():
        messages.warning(request, "Đơn hàng đã được gửi xác nhận hoặc đã hủy trước đó.")
        return redirect('customer_booking_history')

    user_trans_code = request.POST.get('transaction_code', '').strip()
    if not user_trans_code:
        messages.error(request, "Vui lòng nhập mã giao dịch!")
        return redirect('booking_payment', group_code=group_code)

    total_price = sum(b.total_price for b in pending_bookings)
    try:
        with transaction.atomic():
            Transaction.objects.create(
                booking_group_code=group_code,
                user=request.user,
                amount=total_price,
                transaction_reference=user_trans_code,
                is_verified=False,
            )
            pending_bookings.update(status=Booking.Status.WAITING_VERIFY)
        messages.success(request, "Đã gửi xác nhận thanh toán! Vui lòng chờ Admin duyệt trong ít phút.")
        return redirect('home')
    except IntegrityError:
        messages.error(
            request,
            f"Mã giao dịch '{user_trans_code}' đã tồn tại trên hệ thống. Vui lòng kiểm tra lại!",
        )
        return redirect('booking_payment', group_code=group_code)


@require_POST
def cancel_booking_on_leave(request, group_code):
    """Hủy các booking đang chờ thanh toán theo yêu cầu của chủ đơn."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Chưa đăng nhập'}, status=401)

    bookings = Booking.objects.filter(
        group_code=group_code,
        user=request.user,
        status=Booking.Status.PENDING,
    )

    if not bookings.exists():
        return JsonResponse({'success': False, 'error': 'Không tìm thấy đơn hàng chờ thanh toán'}, status=404)

    lock_keys = [
        f"lock:court_{b.court_id}_{b.date.strftime('%Y-%m-%d')}_{b.start_time.strftime('%H:%M')}"
        for b in bookings
    ]
    _release_redis_locks(lock_keys)

    count = bookings.update(status=Booking.Status.ADMIN_CANCELLED)
    return JsonResponse({
        'success': True,
        'message': f'Đã hủy {count} đơn đặt sân',
        'cancelled_count': count,
    })
