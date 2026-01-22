from django.urls import path,include
from . import views

urlpatterns = [
    path('booking_timeline/<uuid:center_id>', views.booking_timeline, name='booking_timeline'),
    path('booking_confirm/', views.booking_confirm, name='booking_confirm'),
]