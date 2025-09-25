# management/templatetags/upload_tags.py
from django import template
from ..forms import EmployeeUploadForm

register = template.Library()

@register.simple_tag
def get_upload_form():
    """
    This template tag returns an instance of the EmployeeUploadForm.
    """
    return EmployeeUploadForm()
