import random
import requests
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_whatsapp(mobile_number, otp):
    url = 'https://api.interakt.ai/v1/public/message/'
    headers = {
        'Authorization': 'Basic UDhqYURhVmhYbEkyd0I5MUxfeDNxSUlDdmFJa3VIV0RBM2hxdW1tWEtlbzo=',
        'Content-Type': 'application/json'
    }
    payload = {
        "countryCode": "+91",
        "phoneNumber": mobile_number,
        "type": "Template",
        "template": {
            "name": "otp_login",
            "languageCode": "en",
            "bodyValues": [otp],
            "buttonValues": {
                "0": [otp]
            }
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    print("INTERAKT API RESPONSE STATUS:", response.status_code)
    print("INTERAKT API RESPONSE BODY:", response.text)
    return response.status_code == 200


def format_hour_label(hour):
    hour_12 = hour % 12 or 12
    am_pm = 'AM' if hour < 12 else 'PM'
    return f"{hour_12}:00 {am_pm}"


def get_employee_next_day_alert_state(employee, now_local=None):
    from .models import EmployeeNextDayAvailability

    start_hour = getattr(settings, 'EMPLOYEE_NEXT_DAY_ALERT_START_HOUR', 16)
    end_hour = getattr(settings, 'EMPLOYEE_NEXT_DAY_ALERT_END_HOUR', 17)

    if not employee:
        return {
            'pending': False,
            'response': None,
            'target_date': None,
            'start_hour': start_hour,
            'end_hour': end_hour,
            'auto_marked': False,
        }

    if now_local is None:
        now_local = timezone.localtime(timezone.now())

    target_date = (now_local + timedelta(days=1)).date()
    start_at = now_local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_at = now_local.replace(hour=end_hour, minute=0, second=0, microsecond=0)

    response = EmployeeNextDayAvailability.objects.filter(
        employee=employee,
        target_date=target_date,
    ).first()
    auto_marked = False

    if now_local >= end_at and response is None:
        response = EmployeeNextDayAvailability.objects.create(
            employee=employee,
            target_date=target_date,
            will_come=False,
            response_source=EmployeeNextDayAvailability.RESPONSE_SOURCE_AUTO,
            responded_at=timezone.now(),
        )
        auto_marked = True

    pending = start_at <= now_local < end_at and response is None

    return {
        'pending': pending,
        'response': response,
        'target_date': target_date,
        'start_hour': start_hour,
        'end_hour': end_hour,
        'auto_marked': auto_marked,
    }
