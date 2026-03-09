"""
Smoke coverage for every API endpoint/method in the project.
"""
from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.comms.models import RiderInAppNotification
from apps.core.models import Order
from tests.factories import (
    MerchantFactory,
    RiderFactory,
    RiderSnapshotFactory,
    UserFactory,
    VerticalFactory,
    ZoneFactory,
)


def _auth_client(username: str, password: str):
    client = APIClient()
    resp = client.post(reverse("auth-login"), {"username": username, "password": password}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return client, resp.data


@pytest.mark.django_db
def test_all_api_endpoints_smoke():
    vertical = VerticalFactory()
    zone = ZoneFactory(vertical=vertical)
    rider = RiderFactory(zone=zone, status="active")
    merchant = MerchantFactory(zone=zone, status="active")
    RiderSnapshotFactory(rider=rider, date=date.today())

    admin = UserFactory(role="super_admin", password="strongpass99")
    admin_client, admin_tokens = _auth_client(admin.username, "strongpass99")

    rider_user = UserFactory(role="rider", rider_profile=rider, password="strongpass99")
    rider_client, _ = _auth_client(rider_user.username, "strongpass99")

    # Auth endpoints
    refresh_resp = admin_client.post(reverse("token-refresh"), {"refresh": admin_tokens["refresh"]}, format="json")
    assert refresh_resp.status_code == 200
    assert admin_client.get(reverse("auth-profile")).status_code == 200
    assert admin_client.patch(reverse("auth-profile"), {"phone": "08012345678"}, format="json").status_code == 200
    assert admin_client.put(
        reverse("auth-profile"),
        {
            "username": admin.username,
            "email": admin.email,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "role": admin.role,
            "phone": "08087654321",
            "vertical": None,
            "zone": None,
            "last_seen": None,
        },
        format="json",
    ).status_code == 200
    assert admin_client.post(
        reverse("auth-change-password"),
        {"old_password": "strongpass99", "new_password": "newstrongpass99"},
        format="json",
    ).status_code == 200
    assert admin_client.post(reverse("auth-fcm-token"), {"firebase_token": "test-fcm-token"}, format="json").status_code == 200
    assert admin_client.post(reverse("auth-logout"), {"refresh": refresh_resp.data["refresh"]}, format="json").status_code == 200

    # Re-login after password change
    admin_client, _ = _auth_client(admin.username, "newstrongpass99")

    # Core readonly/custom endpoints
    assert admin_client.get(reverse("dashboard-summary"), {"period": "today"}).status_code == 200
    assert admin_client.get(reverse("leaderboard"), {"scope": "zones"}).status_code == 200
    assert admin_client.get(reverse("vertical-list")).status_code == 200
    assert admin_client.get(reverse("vertical-detail", kwargs={"pk": vertical.id})).status_code == 200
    assert admin_client.get(reverse("vertical-performance", kwargs={"pk": vertical.id})).status_code == 200
    assert admin_client.get(reverse("zone-list")).status_code == 200
    assert admin_client.get(reverse("zone-detail", kwargs={"pk": zone.id})).status_code == 200
    assert admin_client.get(reverse("zone-performance", kwargs={"pk": zone.id})).status_code == 200
    assert admin_client.get(reverse("rider-list"), {"zone": zone.id}).status_code == 200
    assert admin_client.get(reverse("rider-performance", kwargs={"pk": rider.id})).status_code == 200
    assert admin_client.get(reverse("rider-orders", kwargs={"pk": rider.id})).status_code == 200
    assert admin_client.get(reverse("merchant-list"), {"zone": zone.id}).status_code == 200
    assert admin_client.get(reverse("merchant-performance", kwargs={"pk": merchant.id})).status_code == 200
    assert admin_client.get(reverse("order-list")).status_code == 200

    # Core write endpoints
    rider_create = admin_client.post(
        reverse("rider-list"),
        {
            "zone": zone.id,
            "first_name": "Postman",
            "last_name": "Rider",
            "phone": "08055550001",
            "email": "postman.rider@ae.ng",
            "status": "active",
            "joined_at": str(date.today()),
            "bike_plate": "AE-001",
        },
        format="json",
    )
    assert rider_create.status_code == 201
    rider_id = rider_create.data["id"]
    assert admin_client.get(reverse("rider-detail", kwargs={"pk": rider_id})).status_code == 200
    assert admin_client.patch(reverse("rider-detail", kwargs={"pk": rider_id}), {"status": "inactive"}, format="json").status_code == 200
    assert admin_client.put(
        reverse("rider-detail", kwargs={"pk": rider_id}),
        {
            "zone": zone.id,
            "first_name": "Postman",
            "last_name": "Rider",
            "phone": "08055550001",
            "email": "postman.rider@ae.ng",
            "status": "active",
            "joined_at": str(date.today()),
            "bike_plate": "AE-001",
        },
        format="json",
    ).status_code == 200

    merchant_create = admin_client.post(
        reverse("merchant-list"),
        {
            "zone": zone.id,
            "business_name": "Postman Foods",
            "business_type": "Food",
            "owner_name": "Test Owner",
            "phone": "07055550001",
            "onboarded_at": str(date.today()),
            "status": "active",
        },
        format="json",
    )
    assert merchant_create.status_code == 201
    merchant_id = merchant_create.data["id"]
    assert admin_client.get(reverse("merchant-detail", kwargs={"pk": merchant_id})).status_code == 200
    assert admin_client.patch(reverse("merchant-detail", kwargs={"pk": merchant_id}), {"status": "watch"}, format="json").status_code == 200
    assert admin_client.put(
        reverse("merchant-detail", kwargs={"pk": merchant_id}),
        {
            "zone": zone.id,
            "business_name": "Postman Foods",
            "business_type": "Food",
            "owner_name": "Test Owner",
            "phone": "07055550001",
            "onboarded_at": str(date.today()),
            "status": "active",
        },
        format="json",
    ).status_code == 200

    order_create = admin_client.post(
        reverse("order-list"),
        {
            "reference": "PM-ORDER-001",
            "merchant": merchant.id,
            "zone": zone.id,
            "pickup_address": "1 Pickup Street",
            "delivery_address": "2 Delivery Street",
            "delivery_fee": 1500,
            "order_value": 12000,
        },
        format="json",
    )
    assert order_create.status_code == 201
    order_id = Order.objects.get(reference="PM-ORDER-001").id
    assert admin_client.get(reverse("order-detail", kwargs={"pk": order_id})).status_code == 200
    assert admin_client.patch(reverse("order-detail", kwargs={"pk": order_id}), {"status": "assigned", "rider": rider.id}, format="json").status_code == 200
    assert admin_client.put(
        reverse("order-detail", kwargs={"pk": order_id}),
        {"status": "delivered", "rider": rider.id, "csat_score": 5},
        format="json",
    ).status_code == 200
    assert admin_client.post(reverse("order-assign", kwargs={"pk": order_id}), {"rider_id": rider.id}, format="json").status_code == 200

    # Comms templates endpoints
    assert admin_client.get(reverse("template-list")).status_code == 200
    template_create = admin_client.post(
        reverse("template-list"),
        {"audience": "merchant", "msg_type": "promotion", "label": "Postman Template", "body": "Hello {name}"},
        format="json",
    )
    assert template_create.status_code == 201
    template_id = template_create.data["id"]
    assert admin_client.get(reverse("template-detail", kwargs={"pk": template_id})).status_code == 200
    assert admin_client.patch(reverse("template-detail", kwargs={"pk": template_id}), {"label": "Postman Template v2"}, format="json").status_code == 200
    assert admin_client.put(
        reverse("template-detail", kwargs={"pk": template_id}),
        {
            "audience": "merchant",
            "msg_type": "promotion",
            "label": "Postman Template v3",
            "subject": "Promo",
            "body": "Hello {name}",
            "is_active": True,
        },
        format="json",
    ).status_code == 200

    # Comms broadcasts endpoints
    assert admin_client.get(reverse("broadcast-list")).status_code == 200
    broadcast_create = admin_client.post(
        reverse("broadcast-list"),
        {
            "audience": "merchant",
            "zone": zone.id,
            "recipient_filter": "all",
            "channels": ["sms"],
            "priority": "normal",
            "body": "Broadcast body",
        },
        format="json",
    )
    assert broadcast_create.status_code == 201
    broadcast_id = broadcast_create.data["id"]
    assert admin_client.get(reverse("broadcast-detail", kwargs={"pk": broadcast_id})).status_code == 200
    assert admin_client.patch(reverse("broadcast-detail", kwargs={"pk": broadcast_id}), {"subject": "Updated Subject"}, format="json").status_code == 200
    assert admin_client.put(
        reverse("broadcast-detail", kwargs={"pk": broadcast_id}),
        {
            "audience": "merchant",
            "zone": zone.id,
            "recipient_filter": "all",
            "channels": ["sms"],
            "priority": "high",
            "subject": "Final Subject",
            "body": "Broadcast body final",
        },
        format="json",
    ).status_code == 200
    assert admin_client.get(reverse("broadcast-deliveries", kwargs={"pk": broadcast_id})).status_code == 200
    assert admin_client.post(reverse("broadcast-send", kwargs={"pk": broadcast_id}), format="json").status_code == 200

    # Rider notifications endpoints
    notif = RiderInAppNotification.objects.create(rider=rider, body="Test rider alert")
    assert rider_client.get(reverse("rider-notifications")).status_code == 200
    assert rider_client.post(reverse("notification-read", kwargs={"pk": notif.id}), format="json").status_code == 200

    # Delete endpoints (run last)
    assert admin_client.delete(reverse("template-detail", kwargs={"pk": template_id})).status_code == 204
    assert admin_client.delete(reverse("broadcast-detail", kwargs={"pk": broadcast_id})).status_code == 204
    assert admin_client.delete(reverse("order-detail", kwargs={"pk": order_id})).status_code == 204
    assert admin_client.delete(reverse("merchant-detail", kwargs={"pk": merchant_id})).status_code == 204
    assert admin_client.delete(reverse("rider-detail", kwargs={"pk": rider_id})).status_code == 204
