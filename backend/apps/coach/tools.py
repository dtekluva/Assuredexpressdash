"""
Tool definitions and executor for the APEX AI Coach.

Tools are defined once in Anthropic format (name, description, input_schema).
The OpenAI provider auto-converts them. The executor maps tool names to
axpress_client calls.
"""
import logging

from apps.core import axpress_client
from apps.core.axpress_client import AXpressAPIError

logger = logging.getLogger(__name__)


# ── Tool Definitions (Anthropic format — OpenAI provider converts automatically)

TOOLS = [
    {
        "name": "get_dashboard_summary",
        "description": (
            "Get the top-level OCC dashboard summary: total orders, revenue, "
            "activation rate, open flags, and per-vertical breakdown. "
            "Use this for high-level company performance questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Time period filter",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_verticals",
        "description": (
            "List all verticals with their performance summaries. "
            "Each vertical has a lead, zones, order counts, and revenue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_vertical_detail",
        "description": (
            "Get detailed performance for a specific vertical including "
            "its zones, rider/merchant counts, targets, and gaps. "
            "Use vertical_id from list_verticals results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vertical_id": {"type": "string", "description": "The vertical's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["vertical_id"],
        },
    },
    {
        "name": "get_zone_dashboard",
        "description": (
            "Get dashboard/performance data for a specific zone: orders, revenue, "
            "targets, rider count, merchant count, completion rates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string", "description": "The zone's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_zone_riders",
        "description": (
            "List all riders in a specific zone with their individual performance "
            "metrics: orders completed, acceptance rate, ghost ride ratio, earnings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string", "description": "The zone's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_zone_merchants",
        "description": (
            "List all merchants in a specific zone with their status "
            "(active/watch/inactive), order volume, and revenue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string", "description": "The zone's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_rider_performance",
        "description": (
            "Get detailed performance breakdown for a single rider: "
            "orders, acceptance rate, ghost rides, earnings, salary tier, "
            "target progress, and what they need to reach the next tier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rider_id": {"type": "string", "description": "The rider's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["rider_id"],
        },
    },
    {
        "name": "get_merchant_analytics",
        "description": (
            "Get analytics for a single merchant: order volume, revenue, "
            "activation status, trends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string", "description": "The merchant's ID"},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": ["merchant_id"],
        },
    },
    {
        "name": "get_leaderboard",
        "description": (
            "Get the zone leaderboard ranked by performance. "
            "Shows each zone's orders, revenue, targets, and percentage achieved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_order_analytics",
        "description": (
            "Get order analytics: totals, completion rates, trends over time. "
            "Can filter by zone or vertical."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "past_7_days",
                             "this_month", "last_month", "this_year"],
                    "default": "this_month",
                },
                "zone_id": {
                    "type": "string",
                    "description": "Optional zone ID to filter by",
                },
                "vertical_id": {
                    "type": "string",
                    "description": "Optional vertical ID to filter by",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_zones",
        "description": (
            "List all zones with basic info: name, captain, vertical, "
            "rider/merchant counts. Use this to find zone IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_riders",
        "description": (
            "List all riders with basic info. Supports filtering by zone. "
            "Use this to find rider IDs or get a quick overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Optional zone ID to filter riders by",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_merchants",
        "description": (
            "List all merchants with basic info. Supports filtering by zone. "
            "Use this to find merchant IDs or get a quick overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Optional zone ID to filter merchants by",
                },
            },
            "required": [],
        },
    },
]


# ── Tool Executor ───────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> dict:
    """
    Execute a tool call by dispatching to the appropriate axpress_client method.
    Returns the result dict (or an error dict on failure).
    """
    try:
        period = args.get("period", "this_month")

        if name == "get_dashboard_summary":
            # Dashboard endpoint returns the full summary
            return axpress_client._get(
                "/api/occ/dashboard/",
                axpress_client._period_params(period),
            )

        elif name == "list_verticals":
            return axpress_client.get_verticals(period)

        elif name == "get_vertical_detail":
            return axpress_client.get_vertical_detail(args["vertical_id"], period)

        elif name == "get_zone_dashboard":
            return axpress_client.get_zone_dashboard(args["zone_id"], period)

        elif name == "get_zone_riders":
            return axpress_client.get_zone_riders(args["zone_id"], period)

        elif name == "get_zone_merchants":
            return axpress_client.get_zone_merchants(args["zone_id"], period)

        elif name == "get_rider_performance":
            return axpress_client.get_rider_performance(args["rider_id"], period)

        elif name == "get_merchant_analytics":
            return axpress_client.get_merchant_analytics(args["merchant_id"], period)

        elif name == "get_leaderboard":
            return axpress_client.get_zone_leaderboard(period)

        elif name == "get_order_analytics":
            return axpress_client.get_order_analytics(
                period,
                zone=args.get("zone_id"),
                vertical=args.get("vertical_id"),
            )

        elif name == "list_zones":
            return axpress_client.list_zones()

        elif name == "list_riders":
            params = {}
            if args.get("zone"):
                params["zone"] = args["zone"]
            return axpress_client.list_riders(params)

        elif name == "list_merchants":
            params = {}
            if args.get("zone"):
                params["zone"] = args["zone"]
            return axpress_client.list_merchants(params)

        else:
            return {"error": f"Unknown tool: {name}"}

    except AXpressAPIError as exc:
        logger.warning("Tool %s failed: %s", name, exc)
        return {"error": f"Data fetch failed ({exc.status_code}): {exc.detail[:200]}"}
    except Exception as exc:
        logger.exception("Unexpected error executing tool %s", name)
        return {"error": f"Unexpected error: {str(exc)[:200]}"}
