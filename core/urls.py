# core/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from core.views.dashboard_views import HomepageDashboardView
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('auth_app.urls')),
    path('api/global/', include('auth_app.Purls')),
    path('api/blog/', include('blog.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/admin/', include('user.urls')),
    path('api/', include('messaging.urls')),
    path('api/dashboard/', HomepageDashboardView.as_view(), name='homepage-dashboard'),

    path(
        'feedback/',
        RedirectView.as_view(
            url='https://forms.gle/zTjzmXDamQ9HTyru6',
            permanent=False
        ),
        name='google-feedback-form'
    ),     
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    # Force Django to serve files out of the master roots
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': str(settings.MEDIA_ROOT)}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': str(settings.STATIC_ROOT)}),   
]