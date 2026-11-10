from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    path('partner/register/', views.register_partner, name='register_partner'),
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('booking-history/', views.customer_booking_history, name='customer_booking_history'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset_password'),
]
