from django.shortcuts import render
from partner.models import BadmintonCenter
from django.db.models import Min

def home(request):
    centers = BadmintonCenter.objects.annotate(
        min_price=Min('courts__base_price_per_hour') 
    )
   
    return render(request ,'home/home.html', {'centers': centers, })

def partner_info(request):
    return render(request, 'partner_info.html')
