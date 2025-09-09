from django.apps import AppConfig

class ManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'management'

    def ready(self):
        # Avoid scheduler restart on every app reload in development!
        if hasattr(self, 'scheduler_started'):
            return
        self.scheduler_started = True

        from apscheduler.schedulers.background import BackgroundScheduler
        from . import stale_cleanup
        import atexit

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            stale_cleanup.close_stale_sessions,
            'interval',
            minutes=1,  # Run every 1 minute
            id="close_stale_sessions",
            replace_existing=True,
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
