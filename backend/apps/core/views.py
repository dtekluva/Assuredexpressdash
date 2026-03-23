"""
Core API views for the Assured Express Operations Command Center.

All performance / analytics data is fetched from the main AXpress backend
via authenticated service-to-service API calls (see axpress_client.py).
Results are cached per data type (see cache.py).

Only the Communications app uses a local database — everything else is proxied.
"""
import logging
from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import axpress_client
from .axpress_client import AXpressAPIError
from .cache import cached_axpress_call
from .permissions import IsSuperAdmin

logger = logging.getLogger(__name__)

# Colour palette for verticals (cycled if more than 5)
_VERTICAL_COLORS = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"]


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
            raw = _cached_get_verticals(period)
        except AXpressAPIError as exc:
            return _error_response(exc)

        # If upstream already returns a wrapped object, pass through
        if isinstance(raw, dict) and "verticals" in raw:
            return Response(raw)

        # Otherwise transform the raw verticals array into the shape
        # the frontend expects: { verticals: [...], total_orders, ... }
        raw_list = raw if isinstance(raw, list) else []

        verticals = []
        for i, v in enumerate(raw_list):
            pct = float(v.get("target_attainment_pct", 0) or 0)
            orders = int(v.get("orders_count", 0) or 0)
            revenue = float(v.get("revenue", 0) or 0)
            merchant_count = int(v.get("merchant_count", 0) or 0)
            # Back-calculate target from attainment percentage
            target_orders = round(orders / (pct / 100)) if pct > 0 else 0

            verticals.append({
                "id": v.get("id"),
                "full_name": v.get("name", ""),
                "code": v.get("code", ""),
                "lead_name": v.get("lead_name", ""),
                "lead": v.get("lead"),
                "total_orders": orders,
                "orders_completed": int(v.get("orders_completed", 0) or 0),
                "total_revenue": revenue,
                "pct": pct,
                "target_orders": target_orders,
                "color": _VERTICAL_COLORS[i % len(_VERTICAL_COLORS)],
                "zone_count": int(v.get("zone_count", 0) or 0),
                "rider_count": int(v.get("rider_count", 0) or 0),
                "merchant_count": merchant_count,
            })

        total_orders = sum(v["total_orders"] for v in verticals)
        total_revenue = sum(v["total_revenue"] for v in verticals)
        total_merchants = sum(v["merchant_count"] for v in verticals)
        # Count merchants in verticals that have at least one order
        active_merchants = sum(
            v["merchant_count"] for v in verticals if v["total_orders"] > 0
        )
        activation_rate = (
            round(active_merchants / total_merchants * 100)
            if total_merchants
            else 0
        )

        return Response({
            "verticals": verticals,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_merchants": total_merchants,
            "active_merchants": active_merchants,
            "activation_rate": activation_rate,
            "open_flags": 0,
        })


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

    Returns a single vertical with its zone breakdown, transformed
    into the shape the frontend expects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            raw = _cached_get_vertical_detail(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)

        # If already transformed (has a nested 'vertical' key), pass through
        if isinstance(raw, dict) and "vertical" in raw:
            return Response(raw)

        # Transform raw upstream response into the frontend-expected shape
        aggregates = raw.get("aggregates", {})
        raw_zones = raw.get("zones", [])

        # Determine vertical colour from code position
        code = raw.get("code", "")
        code_idx = ord(code.upper()) - ord("A") if code else 0
        color_hex = _VERTICAL_COLORS[code_idx % len(_VERTICAL_COLORS)]

        # Build zone list — rename merchants_list → merchants (array)
        zones = []
        for z in raw_zones:
            riders = z.get("riders", [])
            # Zone revenue isn't in the upstream response; sum from riders
            zone_revenue = float(z.get("revenue", 0) or 0) or sum(
                float(r.get("revenue", 0) or 0) for r in riders
            )
            zones.append({
                "id": z.get("id"),
                "name": z.get("name", ""),
                "captain": z.get("captain", ""),
                "perf_pct": float(z.get("perf_pct", 0) or 0),
                "orders": int(z.get("orders", 0) or 0),
                "target": int(z.get("target", 0) or 0),
                "target_orders": sum(int(r.get("target_orders", 0) or 0) for r in riders),
                "revenue": zone_revenue,
                "captain_pay": float(z.get("captain_pay", 0) or 0),
                "riders": riders,
                "merchants": z.get("merchants_list", []),
                "merchant_summary": z.get("merchants", {}),
            })

        total_orders = int(aggregates.get("orders", 0) or 0)
        total_revenue = float(aggregates.get("revenue", 0) or 0)

        # Zone targets are REVENUE targets (₦), not order counts
        target_revenue = sum(z["target"] for z in zones)
        pct = round(total_revenue / target_revenue * 100, 1) if target_revenue else 0

        # Order-count targets come from individual riders
        all_riders = [r for z in zones for r in z.get("riders", [])]
        target_orders = sum(int(r.get("target_orders", 0) or 0) for r in all_riders)

        lead_pay = sum(z["captain_pay"] for z in zones)

        return Response({
            "vertical": {
                "id": raw.get("id"),
                "full_name": raw.get("name", ""),
                "code": code,
                "lead_name": raw.get("lead_name", ""),
                "color_hex": color_hex,
            },
            "zones": zones,
            "total_orders": total_orders,
            "target_orders": target_orders,
            "total_revenue": total_revenue,
            "target_revenue": target_revenue,
            "pct": pct,
            "lead_pay": lead_pay,
        })


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


# ── Verticals CRUD ──────────────────────────────────────────────────────────

class VerticalCRUDListView(APIView):
    """GET /api/v1/core/admin/verticals/ — list all verticals (dispatch)
       POST /api/v1/core/admin/verticals/ — create a new vertical
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_verticals_crud(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_vertical(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class VerticalCRUDDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/core/admin/verticals/<id>/"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, pk):
        try:
            data = axpress_client.get_vertical(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_vertical(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def delete(self, request, pk):
        try:
            axpress_client.delete_vertical(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Zones CRUD ──────────────────────────────────────────────────────────────

class ZoneListView(APIView):
    """GET /api/v1/core/zones/?vertical=..."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_zones(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class ZoneCRUDListView(APIView):
    """GET /api/v1/core/admin/zones/ — list all zones
       POST /api/v1/core/admin/zones/ — create a new zone
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_zones(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_zone(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class ZoneCRUDDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/core/admin/zones/<id>/"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, pk):
        try:
            data = axpress_client.get_zone(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_zone(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def delete(self, request, pk):
        try:
            axpress_client.delete_zone(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Zone Targets CRUD ───────────────────────────────────────────────────────

class ZoneTargetListView(APIView):
    """GET /api/v1/core/admin/zone-targets/?zone=...&month=...
       POST /api/v1/core/admin/zone-targets/
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_zone_targets(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_zone_target(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class ZoneTargetDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/core/admin/zone-targets/<id>/"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, pk):
        try:
            data = axpress_client.get_zone_target(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_zone_target(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def delete(self, request, pk):
        try:
            axpress_client.delete_zone_target(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class RiderReassignView(APIView):
    """
    POST /api/v1/core/admin/riders/reassign/

    Move a single rider to a different zone.
    Body: { "rider_id": "<uuid>", "new_zone_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        rider_id = request.data.get("rider_id")
        new_zone_id = request.data.get("new_zone_id")

        if not rider_id or not new_zone_id:
            return Response(
                {"error": "rider_id and new_zone_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = axpress_client.reassign_rider(rider_id, new_zone_id)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class RiderBulkReassignView(APIView):
    """
    POST /api/v1/core/admin/riders/bulk-reassign/

    Move multiple riders to a different zone in one request.
    Body: { "rider_ids": ["<uuid>", ...], "new_zone_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        rider_ids = request.data.get("rider_ids", [])
        new_zone_id = request.data.get("new_zone_id")

        if not rider_ids or not isinstance(rider_ids, list):
            return Response(
                {"error": "rider_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new_zone_id:
            return Response(
                {"error": "new_zone_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = {"succeeded": [], "failed": []}
        for rider_id in rider_ids:
            try:
                axpress_client.reassign_rider(rider_id, new_zone_id)
                results["succeeded"].append(rider_id)
            except AXpressAPIError as exc:
                results["failed"].append({
                    "rider_id": rider_id,
                    "error": exc.detail,
                })

        resp_status = (
            status.HTTP_200_OK if not results["failed"]
            else status.HTTP_207_MULTI_STATUS
        )
        return Response(results, status=resp_status)


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
