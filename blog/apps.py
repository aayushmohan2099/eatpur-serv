from django.apps import AppConfig
import sys


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'

    def ready(self):
        try:
            import blog.signals
        except ImportError:
            pass