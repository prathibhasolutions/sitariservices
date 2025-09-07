from django.http import HttpResponseForbidden
import logging

logger = logging.getLogger(__name__)

ALLOWED_IPS = ['157.48.158.31', '49.37.149.105','49.37.156.241', '127.0.0.1', '152.57.166.217']  # specific IPs
ALLOWED_SUBNETS = ['192.168.29.', '49.37.156']  # subnet prefixes

class RestrictIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        # Allow if IP starts with any allowed subnet prefix OR IP is in the allowed IPs list
        if not (any(ip.startswith(subnet) for subnet in ALLOWED_SUBNETS) or ip in ALLOWED_IPS):
            logger.warning(f"Access denied for IP: {ip}")
            return HttpResponseForbidden("Access denied.")

        response = self.get_response(request)
        return response


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
