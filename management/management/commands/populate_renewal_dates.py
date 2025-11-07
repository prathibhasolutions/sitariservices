from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from management.models import EmployeeUpload


class Command(BaseCommand):
    help = 'Populate renewal_date for all existing EmployeeUpload records'

    def handle(self, *args, **options):
        # Get all EmployeeUpload records that don't have a renewal_date set
        uploads_without_renewal = EmployeeUpload.objects.filter(renewal_date__isnull=True)
        
        count = uploads_without_renewal.count()
        self.stdout.write(f'Found {count} uploads without renewal dates')
        
        updated_count = 0
        for upload in uploads_without_renewal:
            if upload.uploaded_at:
                # Set renewal_date to 1 year from uploaded_at
                upload.renewal_date = (upload.uploaded_at + timedelta(days=365)).date()
                upload.save(update_fields=['renewal_date'])  # Only update renewal_date field
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated_count} EmployeeUpload records with renewal dates'
            )
        )