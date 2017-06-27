import re
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin

from rest_framework.routers import DefaultRouter
import rest_framework.urls

from . import views as v

# 注册所有 DRF 路由

router = DefaultRouter()

routers = []

for key, item in v.__dict__.items():
    if key.endswith('ViewSet'):
        name = key.replace('ViewSet', '')
        name = re.sub(r'([A-Z])', '_\\1', name)[1:].lower()
        if name:
            routers.append((name, item))

for name, item in sorted(routers):
    router.register(name, item)


urlpatterns = [
    url(r'^api-auth/', include(rest_framework.urls, namespace='rest_framework')),
    url(r'^api/', include(router.urls)),
    url(r'^admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)