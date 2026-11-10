import secrets
import string

from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def redirect_back(request, fallback='home'):
    """
    Quay lại trang trước đó một cách an toàn (chặn Open Redirect).
    """
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect(fallback)


def generate_random_password(length):
    """
    Tạo mật khẩu ngẫu nhiên an toàn cho nhân viên.
    """
    alphabet = string.ascii_letters + string.digits

    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            break

    return password
