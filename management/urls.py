from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login_view'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    path('employee/orders/', views.employee_orders_view, name='orders'),
    path('employee/change-password/', views.change_password_view, name='change_password'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('links', views.links_view, name='links'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('calender/', views.calender, name='calender'),
]