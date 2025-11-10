

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('management.urls')),
    # Custom admin login with OTP (must come before admin.site.urls)
    path('admin/', include('management.admin_urls')),
    path('admin/', admin.site.urls),
]


from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
