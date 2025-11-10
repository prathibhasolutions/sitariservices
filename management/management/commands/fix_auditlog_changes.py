from django.core.management.base import BaseCommand
from auditlog.models import LogEntry
from django.db import transaction

class Command(BaseCommand):
    help = 'Fix LogEntry changes field: convert string to dict for auditlog compatibility.'

    def handle(self, *args, **options):
        updated = 0
        with transaction.atomic():
            for entry in LogEntry.objects.all():
                if isinstance(entry.changes, str):
                    entry.changes = {"message": entry.changes}
                    entry.save(update_fields=["changes"])
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} LogEntry records.'))
