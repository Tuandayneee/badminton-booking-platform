from django.urls import path
from . import views

urlpatterns = [
    path('pos/', views.pos_sales, name='pos_sales'),
    path('sales-report/', views.staff_sales_report, name='staff_sales_report'),
    path('service-orders/', views.staff_service_orders, name='staff_service_orders'),
]
