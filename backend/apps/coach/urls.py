from django.urls import path

from .views import CoachChatView

urlpatterns = [
    path("chat/", CoachChatView.as_view(), name="coach-chat"),
]
