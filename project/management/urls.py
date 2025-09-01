from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login_view'),
    path('register/', views.register, name='register'),
    path('password_reset/', views.password_reset, name='password_reset'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    path('employee/notifications/', views.notifications_view, name='notifications'),
    path('employee/orders/', views.employee_orders_view, name='orders'),
    path('employee/change-password/', views.change_password_view, name='change_password'),
]