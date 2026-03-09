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
    UserFactory, VerticalFactory, ZoneFactory, RiderFactory,
    MerchantFactory, RiderSnapshotFactory, ZoneCaptainFactory, VerticalLeadFactory,
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
def zone_setup(db):
    """Create a complete vertical → zone → riders + merchants structure."""
    v     = VerticalFactory()
    zone  = ZoneFactory(vertical=v)
    riders = [RiderFactory(zone=zone) for _ in range(3)]
    merchants = [MerchantFactory(zone=zone) for _ in range(5)]
    return {"vertical": v, "zone": zone, "riders": riders, "merchants": merchants}


@pytest.mark.django_db
class TestDashboardEndpoint:
    def test_returns_200_for_authenticated_user(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_200_OK

    def test_contains_expected_fields(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("dashboard-summary"))
        data = resp.data
        assert "total_orders"     in data
        assert "total_revenue"    in data
        assert "active_riders"    in data
        assert "active_merchants" in data
        assert "verticals"        in data
        assert "period"           in data

    def test_period_filter_today(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("dashboard-summary"), {"period": "today"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["period"]["start"] == date.today()
        assert resp.data["period"]["end"]   == date.today()

    def test_unauthenticated_returns_401(self, db, zone_setup):
        resp = APIClient().get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_zone_captain_only_sees_own_zone(self, db, zone_setup):
        z = zone_setup["zone"]
        captain = ZoneCaptainFactory(zone=z)
        client = APIClient()
        login = client.post(reverse("auth-login"), {"username": captain.username, "password": "testpass123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        resp = client.get(reverse("dashboard-summary"))
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestVerticalEndpoints:
    def test_list_verticals(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("vertical-list"))
        assert resp.status_code == status.HTTP_200_OK
        # At least our test vertical is in results
        assert len(resp.data) >= 1

    def test_vertical_performance(self, admin_client, zone_setup):
        v_id = zone_setup["vertical"].id
        # Create some snapshots
        for rider in zone_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(
            reverse("vertical-performance", kwargs={"pk": v_id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "zones" in resp.data
        assert "total_orders" in resp.data


@pytest.mark.django_db
class TestZoneEndpoints:
    def test_list_zones(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("zone-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_zones_by_vertical(self, admin_client, zone_setup):
        v_id = zone_setup["vertical"].id
        resp = admin_client.get(reverse("zone-list"), {"vertical": v_id})
        assert resp.status_code == status.HTTP_200_OK
        zone_ids = [z["id"] for z in _results(resp.data)]
        assert zone_setup["zone"].id in zone_ids

    def test_zone_performance_returns_riders_and_merchants(self, admin_client, zone_setup):
        z_id = zone_setup["zone"].id
        for rider in zone_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(
            reverse("zone-performance", kwargs={"pk": z_id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "riders"    in resp.data
        assert "merchants" in resp.data
        assert "captain_pay" in resp.data


@pytest.mark.django_db
class TestRiderEndpoints:
    def test_list_riders(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("rider-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_riders_by_zone(self, admin_client, zone_setup):
        z_id = zone_setup["zone"].id
        resp = admin_client.get(reverse("rider-list"), {"zone": z_id})
        returned_ids = [r["id"] for r in _results(resp.data)]
        for rider in zone_setup["riders"]:
            assert rider.id in returned_ids

    def test_rider_performance_endpoint(self, admin_client, zone_setup):
        rider = zone_setup["riders"][0]
        RiderSnapshotFactory(rider=rider, date=date.today())
        resp = admin_client.get(
            reverse("rider-performance", kwargs={"pk": rider.id}),
            {"period": "today"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "orders_completed" in resp.data
        assert "pct"              in resp.data
        assert "flags"            in resp.data

    def test_rider_attainment_pct_calculation(self, admin_client, zone_setup):
        rider = zone_setup["riders"][0]
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
    def test_list_merchants(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("merchant-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_by_status(self, admin_client, zone_setup):
        # Make one merchant inactive
        m = zone_setup["merchants"][0]
        m.status = "inactive"
        m.save()

        resp = admin_client.get(reverse("merchant-list"), {"status": "inactive"})
        assert resp.status_code == status.HTTP_200_OK
        assert any(r["id"] == m.id for r in _results(resp.data))

    def test_create_merchant(self, admin_client, zone_setup):
        zone_id = zone_setup["zone"].id
        payload = {
            "zone":          zone_id,
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
    def test_zone_leaderboard_is_sorted_by_pct(self, admin_client, zone_setup):
        for rider in zone_setup["riders"]:
            RiderSnapshotFactory(rider=rider, date=date.today())

        resp = admin_client.get(reverse("leaderboard"), {"scope": "zones", "period": "today"})
        assert resp.status_code == status.HTTP_200_OK
        pcts = [z["pct"] for z in resp.data]
        assert pcts == sorted(pcts, reverse=True)

    def test_vertical_leaderboard(self, admin_client, zone_setup):
        resp = admin_client.get(reverse("leaderboard"), {"scope": "verticals"})
        assert resp.status_code == status.HTTP_200_OK
