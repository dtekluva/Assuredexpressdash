"""
WebSocket consumers for real-time dashboard updates.
The frontend connects to ws://host/ws/dashboard/ to receive live KPI pushes.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .services import aggregate_zone_summary
from .serializers import get_date_range


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Broadcasts aggregate KPI updates to all connected dashboard clients.
    Group: "dashboard"
    """
    GROUP = "dashboard"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def receive(self, text_data):
        """Client can request a period refresh."""
        data = json.loads(text_data)
        if data.get("action") == "refresh":
            period = data.get("period", "this_month")
            payload = await self.get_summary(period)
            await self.send(text_data=json.dumps(payload))

    async def dashboard_update(self, event):
        """Called by Celery tasks / signals to push live updates."""
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def get_summary(self, period):
        start, end = get_date_range(period)
        return {"type": "summary", "period": period, "timestamp": timezone.now().isoformat()}


class ZoneConsumer(AsyncWebsocketConsumer):
    """
    Per-zone live feed. Zone captains connect here to see live order/rider updates.
    Group: "zone_{zone_id}"
    """
    async def connect(self):
        self.zone_id = self.scope["url_route"]["kwargs"]["zone_id"]
        self.group_name = f"zone_{self.zone_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send current snapshot on connect
        summary = await self.get_zone_summary()
        await self.send(text_data=json.dumps(summary))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def zone_update(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def get_zone_summary(self):
        start, end = get_date_range("today")
        return aggregate_zone_summary(self.zone_id, start, end)
