from django.http import HttpResponseForbidden
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class RestrictIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        
        # Check if IP is allowed
        if not self.is_ip_allowed(ip):
            logger.warning(f"Access denied for IP: {ip}")
            return HttpResponseForbidden("Access denied.")

        response = self.get_response(request)
        return response

    def is_ip_allowed(self, ip):
        # Use caching to avoid database hits on every request
        cache_key = f"allowed_ips_check_{ip}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        # Import here to avoid circular imports
        from management.models import AllowedIP
        
        # Get all active allowed IPs
        allowed_ips = AllowedIP.objects.filter(is_active=True).values_list(
            'ip_address', 'subnet_prefix'
        )
        
        # Check exact IP match or subnet prefix match
        is_allowed = False
        for allowed_ip, subnet_prefix in allowed_ips:
            # Exact IP match
            if ip == allowed_ip:
                is_allowed = True
                break
            
            # Subnet prefix match
            if subnet_prefix and ip.startswith(subnet_prefix):
                is_allowed = True
                break
        
        # Cache the result for 5 minutes to improve performance
        cache.set(cache_key, is_allowed, 300)
        return is_allowed

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
