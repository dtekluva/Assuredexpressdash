from django.contrib import admin
from .models import MessageTemplate, Broadcast, BroadcastDelivery, RiderInAppNotification


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display  = ["label", "audience", "msg_type", "is_active", "created_at"]
    list_filter   = ["audience", "msg_type", "is_active"]
    search_fields = ["label", "body"]


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display  = ["id", "audience", "status", "total_recipients", "open_rate", "sent_at", "created_by"]
    list_filter   = ["audience", "status", "channels"]
    search_fields = ["subject", "body"]
    date_hierarchy = "created_at"
    readonly_fields = ["sent_at", "created_at", "updated_at"]


@admin.register(BroadcastDelivery)
class BroadcastDeliveryAdmin(admin.ModelAdmin):
    list_display  = ["broadcast", "channel", "status", "is_read", "sent_at"]
    list_filter   = ["channel", "status", "is_read"]


@admin.register(RiderInAppNotification)
class RiderInAppNotificationAdmin(admin.ModelAdmin):
    list_display  = ["rider", "priority", "is_read", "created_at"]
    list_filter   = ["priority", "is_read"]
    search_fields = ["rider__first_name", "rider__last_name", "body"]
