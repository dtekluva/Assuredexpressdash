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

    Proxies to the main backend's verticals endpoint and aggregates a
    top-level summary for the OCC landing page.
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

        # Otherwise transform the raw array into the shape the frontend expects
        raw_list = raw if isinstance(raw, list) else []

        zones = []
        for i, v in enumerate(raw_list):
            pct = float(v.get("target_attainment_pct", 0) or 0)
            orders = int(v.get("orders_count", 0) or 0)
            revenue = float(v.get("revenue", 0) or 0)
            merchant_count = int(v.get("merchant_count", 0) or 0)
            target_orders = round(orders / (pct / 100)) if pct > 0 else 0

            zones.append({
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
                "color": _ZONE_COLORS[i % len(_ZONE_COLORS)],
                "hub_count": int(v.get("zone_count", 0) or 0),
                "rider_count": int(v.get("rider_count", 0) or 0),
                "merchant_count": merchant_count,
            })

        total_orders = sum(z["total_orders"] for z in zones)
        total_revenue = sum(z["total_revenue"] for z in zones)
        total_merchants = sum(z["merchant_count"] for z in zones)
        active_merchants = sum(
            z["merchant_count"] for z in zones if z["total_orders"] > 0
        )
        activation_rate = (
            round(active_merchants / total_merchants * 100)
            if total_merchants
            else 0
        )

        return Response({
            "zones": zones,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_merchants": total_merchants,
            "active_merchants": active_merchants,
            "activation_rate": activation_rate,
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

    Returns a single zone with its hub breakdown, transformed
    into the shape the frontend expects.
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

        # Transform raw upstream response into the frontend-expected shape
        aggregates = raw.get("aggregates", {})
        raw_hubs = raw.get("zones", [])

        # Determine zone colour from code position
        code = raw.get("code", "")
        code_idx = ord(code.upper()) - ord("A") if code else 0
        color_hex = _ZONE_COLORS[code_idx % len(_ZONE_COLORS)]

        # Build hub list
        hubs = []
        for h in raw_hubs:
            riders = h.get("riders", [])
            hub_revenue = float(h.get("revenue", 0) or 0) or sum(
                float(r.get("revenue", 0) or 0) for r in riders
            )
            hubs.append({
                "id": h.get("id"),
                "name": h.get("name", ""),
                "captain": h.get("captain", ""),
                "perf_pct": float(h.get("perf_pct", 0) or 0),
                "orders": int(h.get("orders", 0) or 0),
                "target": int(h.get("target", 0) or 0),
                "target_orders": sum(int(r.get("target_orders", 0) or 0) for r in riders),
                "revenue": hub_revenue,
                "captain_pay": float(h.get("captain_pay", 0) or 0),
                "riders": riders,
                "merchants": h.get("merchants_list", []),
                "merchant_summary": h.get("merchants", {}),
            })

        total_orders = int(aggregates.get("orders", 0) or 0)
        total_revenue = float(aggregates.get("revenue", 0) or 0)

        # Hub targets are REVENUE targets (₦), not order counts
        target_revenue = sum(h["target"] for h in hubs)
        pct = round(total_revenue / target_revenue * 100, 1) if target_revenue else 0

        # Order-count targets come from individual riders
        all_riders = [r for h in hubs for r in h.get("riders", [])]
        target_orders = sum(int(r.get("target_orders", 0) or 0) for r in all_riders)

        lead_pay = sum(h["captain_pay"] for h in hubs)

        return Response({
            "zone": {
                "id": raw.get("id"),
                "full_name": raw.get("name", ""),
                "code": code,
                "lead_name": raw.get("lead_name", ""),
                "color_hex": color_hex,
            },
            "hubs": hubs,
            "total_orders": total_orders,
            "target_orders": target_orders,
            "total_revenue": total_revenue,
            "target_revenue": target_revenue,
            "pct": pct,
            "lead_pay": lead_pay,
        })


@cached_axpress_call("zone_detail")
def _cached_get_zone_detail(zone_id, period):
    return axpress_client.get_zone_detail(zone_id, period)


# ── Hubs (was Zones) ────────────────────────────────────────────────────────

class HubDashboardView(APIView):
    """
    GET /api/v1/core/hubs/<id>/dashboard/?period=this_month

    Hub-level KPIs: orders, revenue, rider/merchant counts, targets.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_hub_dashboard(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("hub_dashboard")
def _cached_get_hub_dashboard(hub_id, period):
    return axpress_client.get_hub_dashboard(hub_id, period)


class HubRidersView(APIView):
    """
    GET /api/v1/core/hubs/<id>/riders/?period=this_month

    All riders in a hub with their performance metrics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_hub_riders(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("hub_riders")
def _cached_get_hub_riders(hub_id, period):
    return axpress_client.get_hub_riders(hub_id, period)


class HubMerchantsView(APIView):
    """
    GET /api/v1/core/hubs/<id>/merchants/?period=this_month

    All merchants in a hub with activity status and order metrics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = _period(request)
        try:
            data = _cached_get_hub_merchants(pk, period)
        except AXpressAPIError as exc:
            return _error_response(exc)
        return Response(data)


@cached_axpress_call("hub_merchants")
def _cached_get_hub_merchants(hub_id, period):
    return axpress_client.get_hub_merchants(hub_id, period)


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
