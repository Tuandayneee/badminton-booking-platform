from django.urls import path,include
from . import views

urlpatterns = [
    path('booking_timeline/<uuid:center_id>', views.booking_timeline, name='booking_timeline'),
    path('booking_confirm/', views.booking_confirm, name='booking_confirm'),
    path('booking_save/', views.booking_save, name='booking_save'),
    path('payment/<str:group_code>/', views.booking_payment, name='booking_payment'),
    path('payment/success/<str:group_code>/', views.booking_success_confirm, name='booking_success_confirm'),
    path('payment/cancel/<str:group_code>/', views.cancel_booking_on_leave, name='cancel_booking_on_leave'),
]