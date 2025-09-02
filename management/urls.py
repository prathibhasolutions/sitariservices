from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login_view'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    path('employee/notifications/', views.notifications_view, name='notifications'),
    path('employee/orders/', views.employee_orders_view, name='orders'),
    path('employee/change-password/', views.change_password_view, name='change_password'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('notifications/read/<int:unread_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
]