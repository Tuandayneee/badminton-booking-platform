from django.shortcuts import redirect
import secrets
import string

def redirect_back(request, fallback='home'):
    """
    Quay lại trang trước đó.
    """
    referer = request.META.get('HTTP_REFERER')
    
    if referer:
        return redirect(referer)
    
    return redirect(fallback)

def generate_random_password(length):
    """
    Tạo pass cho nhân viên
    """
    alphabet = string.ascii_letters + string.digits  
    
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password) and 
            any(c.isupper() for c in password) and 
            any(c.isdigit() for c in password)):
            break 
            
    return password