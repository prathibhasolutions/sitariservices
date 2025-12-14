from django.contrib.auth import authenticate, login, get_user_model
from django.shortcuts import render, redirect
from django.contrib import messages
from management.utils import generate_otp, send_otp_whatsapp
from management.models import UserProfile

def admin_login_with_otp(request):
    User = get_user_model()
    # Step 1: Username only
    if request.method == 'GET' or (request.method == 'POST' and 'username' not in request.POST):
        return render(request, 'admin/login_username.html')

    username = request.POST.get('username')
    otp_entered = request.POST.get('otp')
    resend = request.POST.get('resend')
    password = request.POST.get('password')
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        messages.error(request, 'Invalid username.')
        return render(request, 'admin/login_username.html')
    profile = getattr(user, 'profile', None)
    mobile = profile.mobile_number if profile else None
    # Step 2: OTP flow if mobile exists
    if mobile:
        if resend:
            otp = generate_otp()
            request.session['admin_otp'] = otp
            request.session['admin_otp_user'] = user.pk
            send_otp_whatsapp(mobile, otp)
            messages.success(request, f'OTP resent to {mobile}')
            return render(request, 'admin/login_otp.html', {'username': username, 'otp_sent': True})
        if otp_entered:
            expected_otp = request.session.get('admin_otp')
            expected_user = request.session.get('admin_otp_user')
            if str(user.pk) != str(expected_user):
                messages.error(request, 'Session mismatch. Please try again.')
                return redirect('/admin/login/')
            if otp_entered == expected_otp:
                login(request, user)
                request.session.pop('admin_otp', None)
                request.session.pop('admin_otp_user', None)
                return redirect('/admin/')
            else:
                messages.error(request, 'Invalid OTP. Please try again.')
                return render(request, 'admin/login_otp.html', {'username': username, 'otp_sent': True})
        # Initial OTP send after username
        otp = generate_otp()
        request.session['admin_otp'] = otp
        request.session['admin_otp_user'] = user.pk
        send_otp_whatsapp(mobile, otp)
        messages.success(request, f'OTP sent to {mobile}')
        return render(request, 'admin/login_otp.html', {'username': username, 'otp_sent': True})
    # Step 2: Password flow if no mobile
    if password:
        user = authenticate(request, username=username, password=password)
        if user is not None and (user.is_staff or user.is_superuser):
            login(request, user)
            return redirect('/admin/')
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'admin/login_password.html', {'username': username})
    # Show password form if no mobile
    return render(request, 'admin/login_password.html', {'username': username})
