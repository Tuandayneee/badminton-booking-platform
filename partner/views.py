from django.shortcuts import render
from django.contrib.auth.decorators import login_required

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