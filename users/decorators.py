from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*allowed_roles):
    """
    Decorator kiểm tra role của user.
    Kết hợp luôn @login_required, không cần dùng cả 2.
    
    Usage:
        @role_required('partner')
        def partner_dashboard(request): ...
        
        @role_required('staff', 'partner')  # Cho phép nhiều role
        def shared_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role not in allowed_roles:
                messages.error(request, "Bạn không có quyền truy cập trang này.")
                return redirect('home')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
