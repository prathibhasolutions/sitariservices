from django.urls import path
from .admin_otp_login import admin_login_with_otp

urlpatterns = [
    path('admin/login/', admin_login_with_otp, name='admin_login_with_otp'),
]
