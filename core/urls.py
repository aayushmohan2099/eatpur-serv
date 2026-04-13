# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    # path('admin/', admin.site.urls),
    path('api/auth/', include('auth_app.urls')),
    path('api/global/', include('auth_app.Purls')),
    path('api/blog/', include('blog.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)