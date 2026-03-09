"""
Tests for the communications endpoints.
Run:  pytest tests/test_comms.py -v
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import (
    UserFactory, VerticalFactory, ZoneFactory, RiderFactory, MerchantFactory,
)

def _results(data):
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.fixture
def admin_client(db):
    user = UserFactory(role="super_admin")
    client = APIClient()
    resp = client.post(reverse("auth-login"), {"username": user.username, "password": "testpass123"})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return client, user


@pytest.fixture
def zone_with_members(db):
    v = VerticalFactory()
    z = ZoneFactory(vertical=v)
    riders    = [RiderFactory(zone=z) for _ in range(3)]
    merchants = [MerchantFactory(zone=z) for _ in range(5)]
    return {"vertical": v, "zone": z, "riders": riders, "merchants": merchants}


@pytest.mark.django_db
class TestMessageTemplates:
    def test_create_template(self, admin_client):
        client, user = admin_client
        resp = client.post(reverse("template-list"), {
            "audience": "merchant",
            "msg_type": "promotion",
            "label":    "Test Promo",
            "body":     "Hi {name}, we have a special offer for you!",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["label"] == "Test Promo"

    def test_list_templates_filtered_by_audience(self, admin_client):
        client, _ = admin_client
        # Create one of each type
        for aud in ["merchant", "rider"]:
            client.post(reverse("template-list"), {
                "audience": aud, "msg_type": "general",
                "label": f"{aud} template", "body": "Test body",
            })
        resp = client.get(reverse("template-list"), {"audience": "merchant"})
        assert resp.status_code == status.HTTP_200_OK
        assert all(t["audience"] == "merchant" for t in _results(resp.data))

    def test_delete_template(self, admin_client):
        client, _ = admin_client
        create_resp = client.post(reverse("template-list"), {
            "audience": "rider", "msg_type": "performance",
            "label": "Delete Me", "body": "Test", "is_active": True,
        })
        tpl_id = create_resp.data["id"]
        del_resp = client.delete(reverse("template-detail", kwargs={"pk": tpl_id}))
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestBroadcasts:
    def test_create_merchant_broadcast(self, admin_client, zone_with_members):
        client, _ = admin_client
        z = zone_with_members["zone"]
        resp = client.post(reverse("broadcast-list"), {
            "audience":         "merchant",
            "zone":             z.id,
            "recipient_filter": "all",
            "channels":         ["whatsapp", "sms"],
            "subject":          "Test Broadcast",
            "body":             "Hello {name}, here is your message.",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert "id" in resp.data
        assert resp.data["audience"] == "merchant"

    def test_create_rider_broadcast(self, admin_client, zone_with_members):
        client, _ = admin_client
        z = zone_with_members["zone"]
        resp = client.post(reverse("broadcast-list"), {
            "audience":         "rider",
            "zone":             z.id,
            "recipient_filter": "all",
            "channels":         ["inapp"],
            "priority":         "high",
            "body":             "Performance update: {name} you are at {pct}%",
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_broadcast_requires_zone_or_vertical(self, admin_client):
        client, _ = admin_client
        resp = client.post(reverse("broadcast-list"), {
            "audience": "merchant",
            "channels": ["sms"],
            "body":     "Test",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_broadcast_queues_task(self, admin_client, zone_with_members):
        client, _ = admin_client
        z = zone_with_members["zone"]
        create_resp = client.post(reverse("broadcast-list"), {
            "audience": "merchant",
            "zone":     z.id,
            "channels": ["whatsapp"],
            "body":     "Test message",
        })
        bid = create_resp.data["id"]
        # Note: Celery task runs async; in tests it won't actually deliver
        resp = client.post(reverse("broadcast-send", kwargs={"pk": bid}))
        assert resp.status_code == status.HTTP_200_OK
        assert "queued" in resp.data["detail"].lower()

    def test_cannot_send_already_sent_broadcast(self, admin_client, zone_with_members):
        from apps.comms.models import Broadcast
        client, _ = admin_client
        z = zone_with_members["zone"]
        create_resp = client.post(reverse("broadcast-list"), {
            "audience": "merchant",
            "zone":     z.id,
            "channels": ["sms"],
            "body":     "Test",
        })
        bid = create_resp.data["id"]
        Broadcast.objects.filter(id=bid).update(status="sent")
        resp = client.post(reverse("broadcast-send", kwargs={"pk": bid}))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_zone_captain_only_sees_own_broadcasts(self, db, zone_with_members):
        z = zone_with_members["zone"]
        from tests.factories import ZoneCaptainFactory
        captain = ZoneCaptainFactory(zone=z)
        client = APIClient()
        login = client.post(reverse("auth-login"), {"username": captain.username, "password": "testpass123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        # Create a broadcast in another zone
        other_zone = ZoneFactory()
        from apps.comms.models import Broadcast
        Broadcast.objects.create(
            audience="merchant", zone=other_zone, channels=["sms"],
            body="Other zone message", created_by=captain
        )
        resp = client.get(reverse("broadcast-list"))
        assert resp.status_code == status.HTTP_200_OK
        # Captain should not see other zone's broadcast
        assert not any(b.get("zone") == other_zone.id for b in _results(resp.data))


@pytest.mark.django_db
class TestRiderNotifications:
    def test_rider_can_see_own_notifications(self, db, zone_with_members):
        from tests.factories import UserFactory
        from apps.comms.models import RiderInAppNotification
        rider = zone_with_members["riders"][0]
        rider_user = UserFactory(role="rider", rider_profile=rider)

        # Create a notification for this rider
        RiderInAppNotification.objects.create(
            rider=rider, body="You are at 75% target!", priority="normal"
        )

        client = APIClient()
        login = client.post(reverse("auth-login"), {"username": rider_user.username, "password": "testpass123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        resp = client.get(reverse("rider-notifications"))
        assert resp.status_code == status.HTTP_200_OK
        data = _results(resp.data)
        assert len(data) == 1
        assert data[0]["is_read"] is False

    def test_mark_notification_read(self, db, zone_with_members):
        from tests.factories import UserFactory
        from apps.comms.models import RiderInAppNotification
        rider = zone_with_members["riders"][0]
        rider_user = UserFactory(role="rider", rider_profile=rider)
        notif = RiderInAppNotification.objects.create(rider=rider, body="Test", priority="normal")

        client = APIClient()
        login = client.post(reverse("auth-login"), {"username": rider_user.username, "password": "testpass123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        resp = client.post(reverse("notification-read", kwargs={"pk": notif.id}))
        assert resp.status_code == status.HTTP_200_OK
        notif.refresh_from_db()
        assert notif.is_read is True
        assert notif.read_at is not None
