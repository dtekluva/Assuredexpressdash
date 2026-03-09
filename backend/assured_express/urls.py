from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/",      include("apps.authentication.urls")),
    path("api/v1/core/",      include("apps.core.urls")),
    path("api/v1/comms/",     include("apps.comms.urls")),
    path("api/v1/coach/",     include("apps.coach.urls")),

    # OpenAPI docs
    path("api/schema/",         SpectacularAPIView.as_view(),         name="schema"),
    path("api/docs/",           SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/",          SpectacularRedocView.as_view(url_name="schema"),   name="redoc"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
