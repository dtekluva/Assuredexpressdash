from rest_framework import serializers
from .models import MessageTemplate, Broadcast, BroadcastDelivery, RiderInAppNotification


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MessageTemplate
        fields = ["id", "audience", "msg_type", "label", "subject", "body", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class BroadcastCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Broadcast
        fields = [
            "id", "vertical", "zone", "audience", "recipient_filter",
            "channels", "priority", "template", "subject", "body", "scheduled_at",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        vertical = data.get("vertical", getattr(self.instance, "vertical", None))
        zone = data.get("zone", getattr(self.instance, "zone", None))
        if not vertical and not zone:
            raise serializers.ValidationError("Either vertical or zone must be specified.")
        audience = data.get("audience", getattr(self.instance, "audience", None))
        channels = data.get("channels", getattr(self.instance, "channels", []))
        if audience == "rider" and "inapp" not in channels:
            data["channels"] = ["inapp"]
        return data


class BroadcastListSerializer(serializers.ModelSerializer):
    created_by_name  = serializers.CharField(source="created_by.get_full_name", read_only=True)
    total_recipients = serializers.IntegerField(read_only=True)
    open_rate        = serializers.IntegerField(read_only=True)
    scope_name       = serializers.SerializerMethodField()

    class Meta:
        model  = Broadcast
        fields = [
            "id", "audience", "channels", "priority", "subject",
            "status", "scheduled_at", "sent_at", "created_at",
            "created_by_name", "total_recipients", "open_rate", "scope_name",
        ]

    def get_scope_name(self, obj):
        if obj.zone:
            return f"{obj.zone.name} (Zone)"
        if obj.vertical:
            return f"{obj.vertical.name} (Vertical)"
        return "All"


class BroadcastDetailSerializer(BroadcastListSerializer):
    deliveries_summary = serializers.SerializerMethodField()

    class Meta(BroadcastListSerializer.Meta):
        fields = BroadcastListSerializer.Meta.fields + ["body", "recipient_filter", "deliveries_summary"]

    def get_deliveries_summary(self, obj):
        total     = obj.deliveries.count()
        delivered = obj.deliveries.filter(status="delivered").count()
        read      = obj.deliveries.filter(is_read=True).count()
        failed    = obj.deliveries.filter(status="failed").count()
        return {"total": total, "delivered": delivered, "read": read, "failed": failed}


class RiderNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RiderInAppNotification
        fields = ["id", "title", "body", "priority", "is_read", "read_at", "created_at"]
        read_only_fields = ["id", "is_read", "read_at", "created_at"]
