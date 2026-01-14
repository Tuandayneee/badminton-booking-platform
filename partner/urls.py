from django.urls import path,include
from . import views


urlpatterns = [
    path('dashboard/', views.partner_dashboard, name='partner_dashboard'),
    path('courts/', views.courts_management, name='courts_management'),
    path('revenue/', views.revenue_management, name='revenue_management'),
    path('schedule/', views.schedule_management, name='schedule_management'),
    path('customers/', views.customer_management, name='customer_management'),
]