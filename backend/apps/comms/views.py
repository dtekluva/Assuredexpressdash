from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone

from .models import MessageTemplate, Broadcast, BroadcastDelivery, RiderInAppNotification
from .serializers import (
    MessageTemplateSerializer,
    BroadcastCreateSerializer, BroadcastListSerializer, BroadcastDetailSerializer,
    RiderNotificationSerializer,
)
from .tasks import dispatch_broadcast


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for reusable message templates."""
    queryset = MessageTemplate.objects.filter(is_active=True)
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["audience", "msg_type"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BroadcastViewSet(viewsets.ModelViewSet):
    """Create and manage broadcast sends."""
    permission_classes = [IsAuthenticated]
    filterset_fields = ["audience", "status", "zone", "vertical"]

    def get_queryset(self):
        user = self.request.user
        qs = Broadcast.objects.select_related("created_by", "zone", "vertical")
        if user.role == "zone_captain" and user.zone_id:
            return qs.filter(zone_id=user.zone_id)
        if user.role == "vertical_lead" and user.vertical_id:
            return qs.filter(vertical_id=user.vertical_id)
        return qs

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BroadcastCreateSerializer
        if self.action == "retrieve":
            return BroadcastDetailSerializer
        return BroadcastListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """Trigger async delivery of a draft or scheduled broadcast."""
        broadcast = self.get_object()
        if broadcast.status not in (Broadcast.Status.DRAFT, Broadcast.Status.SCHEDULED):
            return Response(
                {"error": "Only draft or scheduled broadcasts can be sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dispatch_broadcast.delay(broadcast.id)
        return Response({"detail": "Broadcast queued for delivery."})

    @action(detail=True, methods=["get"], url_path="deliveries")
    def deliveries(self, request, pk=None):
        broadcast = self.get_object()
        qs = broadcast.deliveries.select_related("merchant", "rider").order_by("-sent_at")
        data = []
        for d in qs:
            recipient = d.merchant.business_name if d.merchant else (d.rider.full_name if d.rider else "—")
            data.append({
                "id": d.id,
                "recipient": recipient,
                "channel": d.channel,
                "status": d.status,
                "is_read": d.is_read,
                "sent_at": d.sent_at,
            })
        return Response(data)


class RiderNotificationListView(generics.ListAPIView):
    """
    GET /api/v1/comms/notifications/
    Returns the calling rider's in-app notifications.
    """
    serializer_class = RiderNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "rider" and user.rider_profile_id:
            return RiderInAppNotification.objects.filter(rider_id=user.rider_profile_id)
        return RiderInAppNotification.objects.none()


class MarkNotificationReadView(APIView):
    """POST /api/v1/comms/notifications/{id}/read/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = self.request.user
        try:
            notif = RiderInAppNotification.objects.get(id=pk, rider_id=user.rider_profile_id)
        except RiderInAppNotification.DoesNotExist:
            return Response({"error": "Not found."}, status=404)
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()

        # Update the delivery read flag too
        if notif.broadcast_id:
            BroadcastDelivery.objects.filter(
                broadcast_id=notif.broadcast_id, rider_id=notif.rider_id
            ).update(is_read=True, read_at=notif.read_at)

        return Response({"detail": "Marked as read."})
