# core/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from core.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    # path('admin/', admin.site.urls),
    path('api/auth/', include('auth_app.urls')),
    path('api/global/', include('auth_app.Purls')),
    path('api/blog/', include('blog.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    # Force Django to serve files out of the master roots
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': str(settings.MEDIA_ROOT)}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': str(settings.STATIC_ROOT)}),
]