from django.apps import AppConfig

class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "blog"
    verbose_name = "Blog System"

    def ready(self):
        """
        Import signals safely.

        IMPORTANT:
        - Keeps import inside ready() to avoid circular imports
        - Wrapped in try/except to prevent crashes during migrations/tests
        """
        try:
            import blog.signals  # noqa: F401
        except ImportError:
            pass
