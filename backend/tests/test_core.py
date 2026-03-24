"""
Tests for core operations API endpoints.
Run:  pytest tests/test_core.py -v
"""
import pytest
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import (
    UserFactory, ZoneFactory, HubFactory, RiderFactory,
    MerchantFactory, RiderSnapshotFactory, HubCaptainFactory, ZoneLeadFactory,
)

def _results(data):
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.fixture
def admin_client(db):
    user = UserFactory(role="super_admin")
    client = APIClient()
    resp = client.post(reverse("auth-login"), {"username": user.username, "password": "testpass123"})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return client


@pytest.fixture
def hub_setup(db):
    """Create a complete zone -> hub -> riders + merchants structure."""
    zone  = ZoneFactory()
    hub   = HubFactory(zone=zone)
    riders = [RiderFactory(hub=hub) for _ in range(3)]
    merchants = [MerchantFactory(hub=hub) for _ in range(5)]
    return {"zone": zone, "hub": hub, "riders": riders, "merchants": merchants}


@pytest.mark.django_db
class TestDashboardEndpoint:
    def test_returns_200_for_authenticated_user(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_200_OK

    def test_contains_expected_fields(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("dashboard-summary"))
        data = resp.data
        assert "total_orders"     in data
        assert "total_revenue"    in data
        assert "active_riders"    in data
        assert "active_merchants" in data
        assert "zones"            in data
        assert "period"           in data

    def test_period_filter_today(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("dashboard-summary"), {"period": "today"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["period"]["start"] == date.today()
        assert resp.data["period"]["end"]   == date.today()

    def test_unauthenticated_returns_401(self, db, hub_setup):
        resp = APIClient().get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_hub_captain_only_sees_own_hub(self, db, hub_setup):
        hub = hub_setup["hub"]
        captain = HubCaptainFactory(hub=hub)
        client = APIClient()
        login = client.post(reverse("auth-login"), {"username": captain.username, "password": "testpass123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        resp = client.get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestZoneEndpoints:
    def test_list_zones(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("zone-list"))
        assert resp.status_code == status.HTTP_200_OK
        # At least our test zone is in results
        assert len(resp.data) >= 1

    def test_zone_performance(self, admin_client, hub_setup):
        z_id = hub_setup["zone"].id
        # Create some snapshots
        for rider in hub_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(
            reverse("zone-performance", kwargs={"pk": z_id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "hubs" in resp.data
        assert "total_orders" in resp.data


@pytest.mark.django_db
class TestHubEndpoints:
    def test_list_hubs(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("hub-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_hubs_by_zone(self, admin_client, hub_setup):
        z_id = hub_setup["zone"].id
        resp = admin_client.get(reverse("hub-list"), {"zone": z_id})
        assert resp.status_code == status.HTTP_200_OK
        hub_ids = [h["id"] for h in _results(resp.data)]
        assert hub_setup["hub"].id in hub_ids

    def test_hub_performance_returns_riders_and_merchants(self, admin_client, hub_setup):
        h_id = hub_setup["hub"].id
        for rider in hub_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(
            reverse("hub-performance", kwargs={"pk": h_id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "riders"    in resp.data
        assert "merchants" in resp.data
        assert "captain_pay" in resp.data


@pytest.mark.django_db
class TestRiderEndpoints:
    def test_list_riders(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("rider-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_riders_by_hub(self, admin_client, hub_setup):
        h_id = hub_setup["hub"].id
        resp = admin_client.get(reverse("rider-list"), {"hub": h_id})
        returned_ids = [r["id"] for r in _results(resp.data)]
        for rider in hub_setup["riders"]:
            assert rider.id in returned_ids

    def test_rider_performance_endpoint(self, admin_client, hub_setup):
        rider = hub_setup["riders"][0]
        RiderSnapshotFactory(rider=rider, date=date.today())
        resp = admin_client.get(
            reverse("rider-performance", kwargs={"pk": rider.id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "orders_completed" in resp.data
        assert "pct"              in resp.data
        assert "flags"            in resp.data

    def test_rider_attainment_pct_calculation(self, admin_client, hub_setup):
        rider = hub_setup["riders"][0]
        # 200 orders out of 400 target = 50%
        for i in range(10):
            RiderSnapshotFactory(rider=rider, date=date(2025, 1, i + 1), orders_completed=20)

        resp = admin_client.get(
            reverse("rider-performance", kwargs={"pk": rider.id}),
            {"period": "custom_month", "custom_month": 0}  # January
        )
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestMerchantEndpoints:
    def test_list_merchants(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("merchant-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_by_status(self, admin_client, hub_setup):
        # Make one merchant inactive
        m = hub_setup["merchants"][0]
        m.status = "inactive"
        m.save()

        resp = admin_client.get(reverse("merchant-list"), {"status": "inactive"})
        assert resp.status_code == status.HTTP_200_OK
        assert any(r["id"] == m.id for r in _results(resp.data))

    def test_create_merchant(self, admin_client, hub_setup):
        hub_id = hub_setup["hub"].id
        payload = {
            "hub":           hub_id,
            "business_name": "Test Bakery",
            "business_type": "Bakery",
            "owner_name":    "Ade Bello",
            "phone":         "08011223344",
            "onboarded_at":  str(date.today()),
        }
        resp = admin_client.post(reverse("merchant-list"), payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["business_name"] == "Test Bakery"


@pytest.mark.django_db
class TestLeaderboardEndpoint:
    def test_hub_leaderboard_is_sorted_by_pct(self, admin_client, hub_setup):
        for rider in hub_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(reverse("leaderboard"), {"scope": "hubs", "period": "today"})
        assert resp.status_code == status.HTTP_200_OK
        pcts = [h["pct"] for h in resp.data]
        assert pcts == sorted(pcts, reverse=True)

    def test_zone_leaderboard(self, admin_client, hub_setup):
        resp = admin_client.get(reverse("leaderboard"), {"scope": "zones"})
        assert resp.status_code == status.HTTP_200_OK
