from django.shortcuts import render,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .forms import BadmintonCenterForm, CourtForm
from django.contrib import messages
from .models import BadmintonCenter,Court

@login_required 
def partner_dashboard(request):
    
    return render(request, 'partner/dashboard.html')

@login_required
def courts_management(request):
    return render(request, 'partner/courts.html')

@login_required
def revenue_management(request):
    return render(request, 'partner/revenue.html')
@login_required
def schedule_management(request):
    return render(request, 'partner/schedule.html')


@login_required
def customer_management(request):
    return render(request, 'partner/customers.html')

@login_required
def centers_management(request):
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    center_form = BadmintonCenterForm()
    return render(request ,'partner/manage_centers.html', {'centers': centers, 'center_form': center_form})
@login_required
def partner_add_center(request):
    if request.method == 'POST':
        form = BadmintonCenterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save(commit=False)
            center.partner = request.user.partner_profile
            center.save()
            form.save_m2m()
            messages.success(request, "Đã thêm trung tâm thành công!")
            return redirect('centers_management')
        else:
            messages.error(request, "có lỗi xảy ra!")
            
    return redirect('centers_management')


@login_required
def partner_edit_center(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        
        form = BadmintonCenterForm(request.POST, request.FILES,instance=center)
        if form.is_valid():
            center = form.save()
            
            
            messages.success(request, "Đã cập nhập thông tin!")
            return redirect('centers_management')
        else:
            messages.error(request, "có lỗi xảy ra!")
            return redirect('partner_centers')
    return redirect('partner_centers')

@login_required
def partner_delete_center(request,center_id):

    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':

        center.delete()
        messages.success(request, f"Đã xóa cơ sở '{center.name}' thành công!")
    return redirect('centers_management')


@login_required
def manage_courts(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    courts = center.courts.all()
    court_form = CourtForm()
    return render(request, 'partner/manage_courts.html', {
        'center': center,
        'courts': courts,
        'court_form': court_form
    })


@login_required
def add_court(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        form = CourtForm(request.POST)
        if form.is_valid():
            court = form.save(commit=False)
            court.center = center
            court.save()
            form.save_m2m()
            messages.success(request, "Đã thêm sân!")
            return redirect('manage_courts', center_id=center_id)
        else:
            messages.error(request, "có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)          

@login_required
def edit_court(request,court_id):
    court = get_object_or_404(Court,id = court_id)
    center_id = court.center.id
    if request.method == 'POST':
        form = CourtForm(request.POST,instance=court)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhập thông tin!")
            return redirect('manage_courts', center_id=center_id)
        else:
            messages.error(request, "có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)

@login_required
def delete_court(request,court_id):
    court = get_object_or_404(Court,id = court_id)
    center_id = court.center.id
    if request.method == 'POST':
        court.delete()
        messages.success(request, "Đã xóa sân!")
    return redirect('manage_courts', center_id=center_id)