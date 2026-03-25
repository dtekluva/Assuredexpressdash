"""
Centralised HTTP client for all outbound calls to the main AXpress backend.
Every OCC view that needs rider/merchant/hub/order/leaderboard data
calls methods here instead of querying a local database.

Auth: Service API key sent as ``Authorization: Bearer sk_...``

NAMING NOTE: The AXpress API still uses old terminology (verticals, zones).
Function names here use the NEW business terminology (zones, hubs) but the
URL paths they call remain unchanged.
"""
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ── Session with retries ─────────────────────────────────────────────────────

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET"],
        )
        _session.mount("https://", HTTPAdapter(max_retries=retries))
        _session.mount("http://", HTTPAdapter(max_retries=retries))
    return _session


# ── Low-level helpers ────────────────────────────────────────────────────────

class AXpressAPIError(Exception):
    """Raised when the main backend returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"AXpress API {status_code}: {detail}")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.AXPRESS_SERVICE_KEY}",
        "Accept": "application/json",
    }


def _url(path: str) -> str:
    """Build full URL, ensuring no double-slashes."""
    base = settings.AXPRESS_BASE_URL.rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    return f"{base}{path}"


def _get(path: str, params: dict | None = None, timeout: int = 30) -> dict:
    """
    Authenticated GET request to the main AXpress backend.
    Returns parsed JSON on success, raises AXpressAPIError otherwise.
    """
    url = _url(path)
    try:
        resp = _get_session().get(url, headers=_headers(), params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("AXpress API error %s %s: %s", status, url, body)
        raise AXpressAPIError(status, body) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("AXpress API connection error: %s", exc)
        raise AXpressAPIError(0, "Connection refused — is the main backend running?") from exc
    except requests.exceptions.Timeout as exc:
        logger.error("AXpress API timeout: %s", url)
        raise AXpressAPIError(0, "Request timed out") from exc


def _post(path: str, data: dict | None = None, timeout: int = 30) -> dict:
    """Authenticated POST request to the main AXpress backend."""
    url = _url(path)
    try:
        resp = _get_session().post(url, headers=_headers(), json=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("AXpress API error %s %s: %s", status, url, body)
        raise AXpressAPIError(status, body) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("AXpress API connection error: %s", exc)
        raise AXpressAPIError(0, "Connection refused — is the main backend running?") from exc
    except requests.exceptions.Timeout as exc:
        logger.error("AXpress API timeout: %s", url)
        raise AXpressAPIError(0, "Request timed out") from exc


def _patch(path: str, data: dict | None = None, timeout: int = 30) -> dict:
    """Authenticated PATCH request to the main AXpress backend."""
    url = _url(path)
    try:
        resp = _get_session().patch(url, headers=_headers(), json=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("AXpress API error %s %s: %s", status, url, body)
        raise AXpressAPIError(status, body) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("AXpress API connection error: %s", exc)
        raise AXpressAPIError(0, "Connection refused — is the main backend running?") from exc
    except requests.exceptions.Timeout as exc:
        logger.error("AXpress API timeout: %s", url)
        raise AXpressAPIError(0, "Request timed out") from exc


def _put(path: str, data: dict | None = None, timeout: int = 30) -> dict:
    """Authenticated PUT request to the main AXpress backend."""
    url = _url(path)
    try:
        resp = _get_session().put(url, headers=_headers(), json=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("AXpress API error %s %s: %s", status, url, body)
        raise AXpressAPIError(status, body) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("AXpress API connection error: %s", exc)
        raise AXpressAPIError(0, "Connection refused — is the main backend running?") from exc
    except requests.exceptions.Timeout as exc:
        logger.error("AXpress API timeout: %s", url)
        raise AXpressAPIError(0, "Request timed out") from exc


def _delete(path: str, timeout: int = 30):
    """Authenticated DELETE request to the main AXpress backend."""
    url = _url(path)
    try:
        resp = _get_session().delete(url, headers=_headers(), timeout=timeout)
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("AXpress API error %s %s: %s", status, url, body)
        raise AXpressAPIError(status, body) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("AXpress API connection error: %s", exc)
        raise AXpressAPIError(0, "Connection refused — is the main backend running?") from exc
    except requests.exceptions.Timeout as exc:
        logger.error("AXpress API timeout: %s", url)
        raise AXpressAPIError(0, "Request timed out") from exc


def _period_params(period: str, **extra) -> dict:
    """Build query-param dict, always including ?period=..."""
    params = {"period": period}
    params.update({k: v for k, v in extra.items() if v is not None})
    return params


# ── Zones & Hubs (AXpress: Zones) ────────────────────────────────────────────

def get_zones(period: str = "this_month"):
    """GET /api/occ/leaderboard/zones/?period=... — all zones with aggregated KPIs."""
    return _get("/api/occ/leaderboard/zones/", _period_params(period))


def get_zone_detail(zone_id, period: str = "this_month"):
    """GET /api/occ/zones/<id>/dashboard/?period=... — zone-level KPIs."""
    return _get(f"/api/occ/zones/{zone_id}/dashboard/", _period_params(period))


def get_zone_riders(zone_id, period: str = "this_month"):
    """GET /api/occ/zones/<id>/riders/?period=... — riders in a zone."""
    return _get(f"/api/occ/zones/{zone_id}/riders/", _period_params(period))


def get_zone_merchants(zone_id, period: str = "this_month"):
    """GET /api/occ/zones/<id>/merchants/?period=... — merchants in a zone."""
    return _get(f"/api/occ/zones/{zone_id}/merchants/", _period_params(period))


# ── Rider Performance ────────────────────────────────────────────────────────

def get_rider_performance(rider_id, period: str = "this_month"):
    """GET /api/occ/riders/<id>/performance/?period=..."""
    return _get(f"/api/occ/riders/{rider_id}/performance/", _period_params(period))


def get_rider_locations():
    """GET /api/occ/riders/locations/ — bulk GPS for map view."""
    return _get("/api/occ/riders/locations/")


# ── Merchant Analytics ───────────────────────────────────────────────────────

def get_merchant_analytics(merchant_id, period: str = "this_month"):
    """GET /api/occ/merchants/<id>/analytics/?period=..."""
    return _get(f"/api/occ/merchants/{merchant_id}/analytics/", _period_params(period))


# ── Leaderboards ─────────────────────────────────────────────────────────────

def get_hub_leaderboard(period: str = "this_month"):
    """Deprecated alias — same as get_zone_leaderboard. Kept for backward compat."""
    return get_zone_leaderboard(period)


def get_zone_leaderboard(period: str = "this_month"):
    """GET /api/occ/leaderboard/zones/?period=... — same as get_zones, kept for leaderboard view."""
    return _get("/api/occ/leaderboard/zones/", _period_params(period))


# ── Order Analytics ──────────────────────────────────────────────────────────

def get_order_analytics(period: str = "this_month", hub=None, zone=None):
    """GET /api/occ/orders/analytics/?period=...&zone=...&vertical=..."""
    return _get(
        "/api/occ/orders/analytics/",
        _period_params(period, zone=hub, vertical=zone),
    )


# ── Dispatch CRUD (proxied to /api/dispatch/*) ──────────────────────────────

# Zones (AXpress: Zones — verticals are deprecated)
def list_zones_crud(params: dict | None = None):
    return _get("/api/dispatch/zones/", params)


def get_zone(zone_id):
    return _get(f"/api/dispatch/zones/{zone_id}/")


def create_zone(data: dict):
    return _post("/api/dispatch/zones/", data)


def update_zone(zone_id, data: dict):
    return _patch(f"/api/dispatch/zones/{zone_id}/", data)


def delete_zone(zone_id):
    return _delete(f"/api/dispatch/zones/{zone_id}/")


# Hubs (AXpress: Zones)
def list_hubs(params: dict | None = None):
    return _get("/api/dispatch/zones/", params)


def get_hub(hub_id):
    return _get(f"/api/dispatch/zones/{hub_id}/")


def create_hub(data: dict):
    return _post("/api/dispatch/zones/", data)


def update_hub(hub_id, data: dict):
    return _patch(f"/api/dispatch/zones/{hub_id}/", data)


def delete_hub(hub_id):
    return _delete(f"/api/dispatch/zones/{hub_id}/")


# Hub Targets (AXpress: Zone Targets)
def list_hub_targets(params: dict | None = None):
    return _get("/api/occ/zone-targets/", params)


def get_hub_target(target_id):
    return _get(f"/api/occ/zone-targets/{target_id}/")


def create_hub_target(data: dict):
    return _post("/api/occ/zone-targets/", data)


def update_hub_target(target_id, data: dict):
    return _patch(f"/api/occ/zone-targets/{target_id}/", data)


def delete_hub_target(target_id):
    return _delete(f"/api/occ/zone-targets/{target_id}/")


# Relay Nodes (physical handoff points within hubs)
def list_relay_nodes(params: dict | None = None):
    """GET /api/dispatch/relay-nodes/"""
    return _get("/api/dispatch/relay-nodes/", params)


def get_relay_node(node_id):
    """GET /api/dispatch/relay-nodes/<id>/"""
    return _get(f"/api/dispatch/relay-nodes/{node_id}/")


def list_relay_nodes_by_hub(hub_id, params: dict | None = None):
    """GET /api/dispatch/relay-nodes/?zone=<hub_id> — AXpress uses 'zone' param."""
    params = params or {}
    params["zone"] = hub_id
    return _get("/api/dispatch/relay-nodes/", params)


# Riders
def list_riders(params: dict | None = None):
    return _get("/api/dispatch/riders/", params)


def get_rider(rider_id):
    return _get(f"/api/dispatch/riders/{rider_id}/")


def create_rider(data: dict):
    return _post("/api/dispatch/riders/", data)


def update_rider(rider_id, data: dict):
    return _patch(f"/api/dispatch/riders/{rider_id}/", data)


def reassign_rider(rider_id, new_relay_node_id):
    """Update a rider's assignment. AXpress now uses 'hub' which points to a RelayNode UUID."""
    return _patch(f"/api/dispatch/riders/{rider_id}/", {"hub": new_relay_node_id})


def get_rider_orders(rider_id, params: dict | None = None):
    """Rider order history from the riders app."""
    return _get(f"/api/riders/orders/history/", params)


# Merchants
def list_merchants(params: dict | None = None):
    return _get("/api/dispatch/merchants/", params)


def get_merchant(merchant_id):
    return _get(f"/api/dispatch/merchants/{merchant_id}/")


def create_merchant(data: dict):
    return _post("/api/dispatch/merchants/", data)


def update_merchant(merchant_id, data: dict):
    return _patch(f"/api/dispatch/merchants/{merchant_id}/", data)


# Orders
def list_orders(params: dict | None = None):
    return _get("/api/dispatch/orders/", params)


def create_order(data: dict):
    return _post("/api/dispatch/orders/", data)


def assign_order(order_id, data: dict):
    return _post(f"/api/dispatch/orders/{order_id}/assign_rider/", data)


def update_order(order_id, data: dict):
    return _patch(f"/api/dispatch/orders/{order_id}/", data)
