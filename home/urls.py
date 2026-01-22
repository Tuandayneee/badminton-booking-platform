
from django.urls import path,include
from .views import home,partner_info
urlpatterns = [
    path('', home ,name='home'),
    path('partner-info/', partner_info, name='partner_info'),
]