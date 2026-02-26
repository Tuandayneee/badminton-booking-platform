from django.urls import path,include
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    path('partner/register/', views.register_partner, name='register_partner'),
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('booking-history/', views.customer_booking_history, name='customer_booking_history'),
]