from django.contrib import admin
from .models import (
    Employee,
    AttendanceSession,
    Application,
    Commission,
    Department,
    Invoice,
    Particular,
    BreakSession,
    Worksheet,
)

# Register all models for admin site access
admin.site.register(Employee)
admin.site.register(AttendanceSession)
admin.site.register(Application)
admin.site.register(Commission)
admin.site.register(Department)
admin.site.register(Invoice)
admin.site.register(Particular)
admin.site.register(BreakSession)
admin.site.register(Worksheet)


from django.contrib import admin
from .models import AllowedIP

@admin.register(AllowedIP)
class AllowedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'subnet_prefix', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('ip_address', 'subnet_prefix', 'description')
    list_editable = ('is_active',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('IP Configuration', {
            'fields': ('ip_address', 'subnet_prefix', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Clear cache when IP settings change
        from django.core.cache import cache
        cache.clear()
