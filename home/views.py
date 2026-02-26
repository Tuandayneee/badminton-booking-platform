from django.shortcuts import render, redirect
from partner.models import BadmintonCenter
from django.db.models import Min

def home(request):
    # Chặn partner và staff truy cập trang home
    if request.user.is_authenticated:
        if request.user.role == 'partner':
            return redirect('partner_dashboard')
        elif request.user.role == 'staff':
            return redirect('pos_sales')
    
    centers = BadmintonCenter.objects.annotate(
        min_price=Min('courts__base_price_per_hour') 
    )
   
    return render(request ,'home/home.html', {'centers': centers, })

def partner_info(request):
    return render(request, 'home/partner_info.html')
