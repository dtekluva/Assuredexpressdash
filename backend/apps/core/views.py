"""
Core API views for the Assured Express Operations Command Center.

All performance / analytics data is fetched from the main AXpress backend
via authenticated service-to-service API calls (see axpress_client.py).
Results are cached per data type (see cache.py).

Only the Communications app uses a local database — everything else is proxied.

NAMING: Views use new business terminology (Zone = old Vertical, Hub = old Zone).
The axpress_client translates to AXpress API's old naming internally.
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

# Colour palette for zones (cycled if more than 5)
_ZONE_COLORS = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"]


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

    Fetches from the zone leaderboard endpoint (/api/occ/leaderboard/zones/)
    and transforms it into the dashboard summary the frontend expects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        try:
            raw = _cached_get_zones(period)
        except AXpressAPIError as exc:
            return _error_response(exc)

        # If upstream already returns a wrapped object, pass through
        if isinstance(raw, dict) and "zones" in raw:
            return Response(raw)

        # Transform the leaderboard array into the dashboard shape
        raw_list = raw if isinstance(raw, list) else []

        zones = []
        for i, v in enumerate(raw_list):
            orders = int(v.get("orders", 0) or 0)
            revenue = float(v.get("revenue", 0) or 0)
            target = int(v.get("target", 0) or 0)
            pct = float(v.get("target_pct", 0) or 0)

            zones.append({
                "id": v.get("zone_id"),
                "full_name": v.get("zone_name", ""),
                "code": chr(ord("A") + i),
                "lead_name": v.get("captain", ""),
                "lead": None,
                "total_orders": orders,
                "orders_completed": orders,
                "total_revenue": revenue,
                "pct": pct,
                "target_orders": target,
                "color": v.get("color") or _ZONE_COLORS[i % len(_ZONE_COLORS)],
                "hub_count": 0,
                "rider_count": 0,
                "merchant_count": 0,
                "earnings": v.get("earnings"),
                "rank": v.get("rank"),
            })

        total_orders = sum(z["total_orders"] for z in zones)
        total_revenue = sum(z["total_revenue"] for z in zones)

        return Response({
            "zones": zones,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_merchants": 0,
            "active_merchants": 0,
            "activation_rate": 0,
            "open_flags": 0,
        })


@cached_axpress_call("zones")
def _cached_get_zones(period):
    return axpress_client.get_zones(period)


# ── Zones (was Verticals) ───────────────────────────────────────────────────

class ZoneListView(APIView):
    """
    GET /api/v1/core/zones/?period=this_month

    Returns all zones with aggregated KPIs from the main backend.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        try:
            data = _cached_get_zones(period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class ZoneDetailView(APIView):
    """
    GET /api/v1/core/zones/<id>/?period=this_month

    Returns zone-level KPIs from /api/occ/zones/{id}/dashboard/
    plus relay nodes from /api/dispatch/relay-nodes/?zone={id}.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            raw = _cached_get_zone_detail(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)

        # If already transformed (has a nested 'zone' key), pass through
        if isinstance(raw, dict) and "zone" in raw:
            return Response(raw)

        # Fetch relay nodes for this zone
        try:
            relay_nodes = axpress_client.list_relay_nodes_by_hub(pk)
        except AXpressAPIError:
            relay_nodes = []

        relay_nodes_list = relay_nodes if isinstance(relay_nodes, list) else []

        # Extract KPIs from the zone dashboard response
        total_orders = int(raw.get("orders_total", 0) or raw.get("orders", 0) or 0)
        orders_completed = int(raw.get("orders_completed", 0) or 0)
        total_revenue = float(raw.get("revenue", 0) or 0)
        rider_count = int(raw.get("rider_count", 0) or 0)
        active_riders = int(raw.get("active_riders", 0) or 0)
        merchant_count = int(raw.get("merchant_count", 0) or 0)
        active_merchants = int(raw.get("active_merchants", 0) or 0)
        target_pct = float(raw.get("target_attainment_pct", 0) or 0)
        target_orders = int(raw.get("target", 0) or 0)

        # Determine zone colour from index (fetch zone list for context)
        # Use a default; frontend can override
        color_hex = raw.get("color") or _ZONE_COLORS[0]

        return Response({
            "zone": {
                "id": pk,
                "full_name": raw.get("zone_name", raw.get("name", "")),
                "code": raw.get("code", ""),
                "lead_name": raw.get("captain", raw.get("lead_name", "")),
                "color_hex": color_hex,
            },
            "relay_nodes": relay_nodes_list,
            "total_orders": total_orders,
            "orders_completed": orders_completed,
            "target_orders": target_orders,
            "total_revenue": total_revenue,
            "target_pct": target_pct,
            "rider_count": rider_count,
            "active_riders": active_riders,
            "merchant_count": merchant_count,
            "active_merchants": active_merchants,
            "avg_delivery_time": raw.get("avg_delivery_time"),
            "avg_distance_km": raw.get("avg_distance_km"),
        })


@cached_axpress_call("zone_detail")
def _cached_get_zone_detail(zone_id, period):
    return axpress_client.get_zone_detail(zone_id, period)


# ── Zone Riders & Merchants ─────────────────────────────────────────────────

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


# ── Relay Nodes ──────────────────────────────────────────────────────────────

class RelayNodeListView(APIView):
    """
    GET /api/v1/core/relay-nodes/?hub=...

    List relay nodes, optionally filtered by hub.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = dict(request.query_params)
        # Translate 'hub' param to 'zone' for AXpress API
        if "hub" in params:
            params["zone"] = params.pop("hub")
        try:
            data = _cached_get_relay_nodes(str(params))
            if data is None:
                data = axpress_client.list_relay_nodes(params)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class RelayNodeDetailView(APIView):
    """
    GET /api/v1/core/relay-nodes/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            data = axpress_client.get_relay_node(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("relay_nodes")
def _cached_get_relay_nodes(params_key):
    # This is a pass-through; the actual call happens in the view
    # We cache based on the stringified params
    return None


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
    GET /api/v1/core/leaderboard/?period=this_month&scope=hubs

    Hub and zone leaderboards with earnings drill-down.
    scope: "hubs" (default) or "zones"
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        scope = request.query_params.get("scope", "hubs")
        try:
            if scope == "zones":
                data = _cached_get_zone_leaderboard(period)
            else:
                data = _cached_get_hub_leaderboard(period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("leaderboard")
def _cached_get_hub_leaderboard(period):
    return axpress_client.get_hub_leaderboard(period)


@cached_axpress_call("leaderboard")
def _cached_get_zone_leaderboard(period):
    return axpress_client.get_zone_leaderboard(period)


# ── Order Analytics ──────────────────────────────────────────────────────────

class OrderAnalyticsView(APIView):
    """
    GET /api/v1/core/orders/analytics/?period=this_month&hub=...&zone=...

    Aggregated order metrics: totals, revenue, by-hub breakdown, by-hour.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = _period(request)
        hub = request.query_params.get("hub")
        zone = request.query_params.get("zone")
        try:
            data = _cached_get_order_analytics(period, hub, zone)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("order_analytics")
def _cached_get_order_analytics(period, hub=None, zone=None):
    return axpress_client.get_order_analytics(period, hub=hub, zone=zone)


# ═════════════════════════════════════════════════════════════════════════════
# CRUD Proxy Views — dispatch endpoints on the main backend
# ═════════════════════════════════════════════════════════════════════════════


# ── Zones CRUD (AXpress: Verticals) ─────────────────────────────────────────

class ZoneCRUDListView(APIView):
    """GET /api/v1/core/admin/zones/ — list all zones (dispatch)
       POST /api/v1/core/admin/zones/ — create a new zone
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_zones_crud(dict(request.query_params))
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


# ── Hubs CRUD (AXpress: Zones) ──────────────────────────────────────────────

class HubListView(APIView):
    """GET /api/v1/core/hubs/?zone=..."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = axpress_client.list_hubs(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class HubCRUDListView(APIView):
    """GET /api/v1/core/admin/hubs/ — list all hubs
       POST /api/v1/core/admin/hubs/ — create a new hub
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_hubs(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_hub(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class HubCRUDDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/core/admin/hubs/<id>/"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, pk):
        try:
            data = axpress_client.get_hub(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_hub(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def delete(self, request, pk):
        try:
            axpress_client.delete_hub(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Hub Targets CRUD (AXpress: Zone Targets) ────────────────────────────────

class HubTargetListView(APIView):
    """GET /api/v1/core/admin/hub-targets/?hub=...&month=...
       POST /api/v1/core/admin/hub-targets/
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            data = axpress_client.list_hub_targets(dict(request.query_params))
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def post(self, request):
        try:
            data = axpress_client.create_hub_target(request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class HubTargetDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/core/admin/hub-targets/<id>/"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, pk):
        try:
            data = axpress_client.get_hub_target(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def patch(self, request, pk):
        try:
            data = axpress_client.update_hub_target(pk, request.data)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)

    def delete(self, request, pk):
        try:
            axpress_client.delete_hub_target(pk)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Riders CRUD ──────────────────────────────────────────────────────────────

class RiderListView(APIView):
    """GET /api/v1/core/riders/?hub=...&status=..."""
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

    Move a single rider to a different hub.
    Body: { "rider_id": "<uuid>", "new_hub_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        rider_id = request.data.get("rider_id")
        new_hub_id = request.data.get("new_hub_id")

        if not rider_id or not new_hub_id:
            return Response(
                {"error": "rider_id and new_hub_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = axpress_client.reassign_rider(rider_id, new_hub_id)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


class RiderBulkReassignView(APIView):
    """
    POST /api/v1/core/admin/riders/bulk-reassign/

    Move multiple riders to a different hub in one request.
    Body: { "rider_ids": ["<uuid>", ...], "new_hub_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        rider_ids = request.data.get("rider_ids", [])
        new_hub_id = request.data.get("new_hub_id")

        if not rider_ids or not isinstance(rider_ids, list):
            return Response(
                {"error": "rider_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new_hub_id:
            return Response(
                {"error": "new_hub_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = {"succeeded": [], "failed": []}
        for rider_id in rider_ids:
            try:
                axpress_client.reassign_rider(rider_id, new_hub_id)
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
