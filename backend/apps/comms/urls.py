from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MessageTemplateViewSet, BroadcastViewSet,
    RiderNotificationListView, MarkNotificationReadView,
)

router = DefaultRouter()
router.register(r"templates",  MessageTemplateViewSet, basename="template")
router.register(r"broadcasts", BroadcastViewSet,       basename="broadcast")

urlpatterns = [
    path("", include(router.urls)),
    path("notifications/",           RiderNotificationListView.as_view(),  name="rider-notifications"),
    path("notifications/<int:pk>/read/", MarkNotificationReadView.as_view(), name="notification-read"),
]
