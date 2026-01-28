from django.urls import path,include
from . import views


urlpatterns = [
    path('dashboard/', views.partner_dashboard, name='partner_dashboard'),
   # path('courts/', views.courts_management, name='courts_management'),
    path('revenue/', views.revenue_management, name='revenue_management'),
    path('schedule/<uuid:center_id>/', views.schedule_management, name='schedule_management'),
    path('customers/<uuid:center_id>/', views.customer_management, name='customer_management'),
    path('centers/', views.centers_management, name='centers_management'),
    path('add_center/', views.partner_add_center, name='partner_add_center'),
    path('centers/edit/<uuid:center_id>', views.partner_edit_center, name='partner_edit_center'),
    path('centers/delete/<uuid:center_id>', views.partner_delete_center, name='partner_delete_center'),
    path('centers/<uuid:center_id>/courts/', views.manage_courts, name='manage_courts'),
    path('centers/<uuid:center_id>/courts/add/', views.add_court, name='add_court'),
    path('centers/courts/edit/<int:court_id>', views.edit_court, name='edit_court'),
    path('centers/courts/delete/<int:court_id>', views.delete_court, name='delete_court'),
    path('transactions/', views.transactions_management, name='partner_transactions'),
    path('transactions/approve/<int:transaction_id>/', views.approve_transaction, name='partner_approve_transaction'),
]