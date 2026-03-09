"""
Core API views for the Assured Express Operations Command Center.

All performance / analytics data is fetched from the main AXpress backend
via authenticated service-to-service API calls (see axpress_client.py).
Results are cached per data type (see cache.py).

Only the Communications app uses a local database — everything else is proxied.
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import axpress_client
from .axpress_client import AXpressAPIError
from .cache import cached_axpress_call

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _period(request) -> str:
    """Extract the period query param (forwarded straight to main backend)."""
    return request.query_params.get("period", "this_month")


def _error_response(exc: AXpressAPIError):
    """Translate an AXpress API error into a DRF Response."""
    if exc.status_code == 0:
        return Response(
            {"error": "Main backend unavailable", "detail": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(
        {"error": "Upstream error", "detail": exc.detail},
        status=exc.status_code or status.HTTP_502_BAD_GATEWAY,
    )


# ── Dashboard Summary ────────────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    """
    GET /api/v1/core/dashboard/?period=this_month

    Proxies to the main backend's verticals endpoint and aggregates a
    top-level summary for the OCC landing page.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        try:
            data = _cached_get_verticals(period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("verticals")
def _cached_get_verticals(period):
    return axpress_client.get_verticals(period)


# ── Verticals ────────────────────────────────────────────────────────────────

class VerticalListView(APIView):
    """
    GET /api/v1/core/verticals/?period=this_month

    Returns all verticals with aggregated KPIs from the main backend.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        try:
            data = _cached_get_verticals(period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class VerticalDetailView(APIView):
    """
    GET /api/v1/core/verticals/<id>/?period=this_month

    Returns a single vertical with its zone breakdown.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_vertical_detail(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("vertical_detail")
def _cached_get_vertical_detail(vertical_id, period):
    return axpress_client.get_vertical_detail(vertical_id, period)


# ── Zones ────────────────────────────────────────────────────────────────────

class ZoneDashboardView(APIView):
    """
    GET /api/v1/core/zones/<id>/dashboard/?period=this_month

    Zone-level KPIs: orders, revenue, rider/merchant counts, targets.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_zone_dashboard(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("zone_dashboard")
def _cached_get_zone_dashboard(zone_id, period):
    return axpress_client.get_zone_dashboard(zone_id, period)


class ZoneRidersView(APIView):
    """
    GET /api/v1/core/zones/<id>/riders/?period=this_month

    All riders in a zone with their performance metrics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_zone_riders(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("zone_riders")
def _cached_get_zone_riders(zone_id, period):
    return axpress_client.get_zone_riders(zone_id, period)


class ZoneMerchantsView(APIView):
    """
    GET /api/v1/core/zones/<id>/merchants/?period=this_month

    All merchants in a zone with activity status and order metrics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_zone_merchants(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("zone_merchants")
def _cached_get_zone_merchants(zone_id, period):
    return axpress_client.get_zone_merchants(zone_id, period)


# ── Rider Performance ────────────────────────────────────────────────────────

class RiderPerformanceView(APIView):
    """
    GET /api/v1/core/riders/<id>/performance/?period=this_month

    Full 9-metric rider profile: KM/revenue ratio, ghost-ride detection,
    peak hour utilisation, acceptance rate, CSAT, etc.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_rider_performance(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("rider_performance")
def _cached_get_rider_performance(rider_id, period):
    return axpress_client.get_rider_performance(rider_id, period)


class RiderLocationsView(APIView):
    """
    GET /api/v1/core/riders/locations/

    Bulk GPS positions for all riders — used by the map view.
    Short cache TTL (30s) for near real-time updates.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = _cached_get_rider_locations()
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("rider_locations")
def _cached_get_rider_locations():
    return axpress_client.get_rider_locations()


# ── Merchant Analytics ───────────────────────────────────────────────────────

class MerchantAnalyticsView(APIView):
    """
    GET /api/v1/core/merchants/<id>/analytics/?period=this_month

    Merchant performance: orders, revenue, fulfillment rate, activity status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_merchant_analytics(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("merchant_analytics")
def _cached_get_merchant_analytics(merchant_id, period):
    return axpress_client.get_merchant_analytics(merchant_id, period)


# ── Leaderboards ─────────────────────────────────────────────────────────────

class LeaderboardView(APIView):
    """
    GET /api/v1/core/leaderboard/?period=this_month&scope=zones

    Zone and vertical leaderboards with earnings drill-down.
    scope: "zones" (default) or "verticals"
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        scope = request.query_params.get("scope", "zones")
        try:
            if scope == "verticals":
                data = _cached_get_vertical_leaderboard(period)
            else:
                data = _cached_get_zone_leaderboard(period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("leaderboard")
def _cached_get_zone_leaderboard(period):
    return axpress_client.get_zone_leaderboard(period)


@cached_axpress_call("leaderboard")
def _cached_get_vertical_leaderboard(period):
    return axpress_client.get_vertical_leaderboard(period)


# ── Order Analytics ──────────────────────────────────────────────────────────

class OrderAnalyticsView(APIView):
    """
    GET /api/v1/core/orders/analytics/?period=this_month&zone=...&vertical=...

    Aggregated order metrics: totals, revenue, by-zone breakdown, by-hour.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        zone = request.query_params.get("zone")
        vertical = request.query_params.get("vertical")
        try:
            data = _cached_get_order_analytics(period, zone, vertical)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("order_analytics")
def _cached_get_order_analytics(period, zone=None, vertical=None):
    return axpress_client.get_order_analytics(period, zone=zone, vertical=vertical)


# ═════════════════════════════════════════════════════════════════════════════
# CRUD Proxy Views — dispatch endpoints on the main backend
# These restore the original endpoints the frontend expects for listing,
# creating, and updating riders, merchants, orders, and zones.
# ═════════════════════════════════════════════════════════════════════════════


# ── Zones (list) ─────────────────────────────────────────────────────────────

class ZoneListView(APIView):
    """GET /api/v1/core/zones/?vertical=..."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_zones(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


# ── Riders CRUD ──────────────────────────────────────────────────────────────

class RiderListView(APIView):
    """GET /api/v1/core/riders/?zone=...&status=..."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_riders(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_rider(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class RiderDetailView(APIView):
    """GET/PATCH /api/v1/core/riders/<id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            data = axpress_client.get_rider(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_rider(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class RiderOrdersView(APIView):
    """GET /api/v1/core/riders/<id>/orders/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            params = dict(request.query_params)
            params["rider"] = pk
            data = axpress_client.list_orders(params)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


# ── Merchants CRUD ───────────────────────────────────────────────────────────

class MerchantListView(APIView):
    """GET/POST /api/v1/core/merchants/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_merchants(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_merchant(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class MerchantDetailView(APIView):
    """GET/PATCH /api/v1/core/merchants/<id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            data = axpress_client.get_merchant(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_merchant(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


# ── Orders CRUD ──────────────────────────────────────────────────────────────

class OrderListView(APIView):
    """GET/POST /api/v1/core/orders/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_orders(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_order(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """PATCH /api/v1/core/orders/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            data = axpress_client.update_order(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class OrderAssignView(APIView):
    """POST /api/v1/core/orders/<id>/assign/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            data = axpress_client.assign_order(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)
