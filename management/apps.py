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

        # Import auditlog signal handlers for IP logging
        import management.auditlog_signals
        import management.auditlog_auth_signals

        # Register models with auditlog for tracking
        from auditlog.registry import auditlog
        from . import models

        # List all model classes to register for audit logging
        # Automatically register all models in management.models with auditlog
        import inspect
        model_classes = []
        for name, obj in inspect.getmembers(models):
            if inspect.isclass(obj) and issubclass(obj, models.models.Model) and obj.__module__ == models.__name__:
                model_classes.append(obj)
        for model in model_classes:
            auditlog.register(model)


