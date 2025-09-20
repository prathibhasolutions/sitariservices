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
        from management.models import AllowedIP
        from django.core.cache import cache

        # --- 1. Check for the global 'Block All' rule FIRST ---
        global_block_key = "ip_restriction_global_block_status"
        is_globally_blocked = cache.get(global_block_key)
        if is_globally_blocked is None:
            # Look for the specific description
            is_globally_blocked = AllowedIP.objects.filter(description='GLOBAL_BLOCK', is_active=True).exists()
            cache.set(global_block_key, is_globally_blocked, 300)
        
        if is_globally_blocked:
            return False # If this rule exists, block everyone.

        # --- 2. If not blocked, check for the global 'Allow All' rule ---
        global_allow_key = "ip_restriction_global_allow_status"
        is_globally_allowed = cache.get(global_allow_key)
        if is_globally_allowed is None:
            # Look for the specific description
            is_globally_allowed = AllowedIP.objects.filter(description='GLOBAL_ALLOW_ALL', is_active=True).exists()
            cache.set(global_allow_key, is_globally_allowed, 300)
        
        if is_globally_allowed:
            return True # If this rule exists, allow everyone.

        # --- 3. If no global rules, fall back to checking the IP list ---
        cache_key = f"allowed_ips_check_{ip}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Exclude global rules from the specific IP check
        allowed_ips = AllowedIP.objects.filter(is_active=True)\
            .exclude(description__in=['GLOBAL_ALLOW_ALL', 'GLOBAL_BLOCK'])\
            .values_list('ip_address', 'subnet_prefix')
        
        is_allowed = False
        for allowed_ip, subnet_prefix in allowed_ips:
            if ip == allowed_ip or (subnet_prefix and ip.startswith(subnet_prefix)):
                is_allowed = True
                break
                
        cache.set(cache_key, is_allowed, 300)
        return is_allowed



def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
