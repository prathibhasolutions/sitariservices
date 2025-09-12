from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_with_otp, name='login'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('links', views.links_view, name='links'),
   path('applications/', views.application_list_create_view, name='applications'),
    path('applications/<int:pk>/', views.application_detail_view, name='application-detail'),
    path('employee/attendance_ping/', views.attendance_ping, name='attendance_ping'),
    path('worksheet/', views.worksheet_view, name='worksheet'),
    path('worksheet/edit/<int:entry_id>/', views.worksheet_entry_edit_view, name='worksheet-edit'),
    
]

