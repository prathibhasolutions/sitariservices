from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_with_otp, name='login'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('links', views.links_view, name='links'),
    path('calender/', views.calender, name='calender'),
    path('contact/', views.contact, name='contact'),
    path('workorders/', views.work_order_list_create_view, name='workorders'),
    path('workorders/<int:pk>/', views.work_order_detail_view, name='workorder-detail'),
    
]

