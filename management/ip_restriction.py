from django.http import HttpResponseForbidden

ALLOWED_IPS = ['157.48.158.31', '49.37.149.105']  # e.g., ['192.168.1.20', '203.0.113.5']

class RestrictIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        if ip not in ALLOWED_IPS:
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
