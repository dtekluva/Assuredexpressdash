"""
APEX AI Coach — chat endpoint.

POST /api/v1/coach/chat/
  Body: { "messages": [...], "period": "this_month" }
  Returns: { "reply": "...", "tool_calls": [...] }
"""
import logging

import httpx
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import get_provider
from .tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are APEX, the AI operations coach for Assured Express Logistics — a last-mile delivery company in Lagos, Nigeria.

ROLE:
- You help operations staff (zone captains, vertical leads, the CEO) understand performance, spot problems, and take action.
- You give direct, specific, actionable advice grounded in real data.
- You understand Nigerian logistics, informal sector dynamics, and commission-based rider compensation.

COMPANY STRUCTURE:
- 4 verticals, each led by a vertical lead: Dennis (Island/Lekki), Seun (Central Mainland), Mary (North/Ikorodu), Erinfolami (Southwest)
- 20 zones across Lagos, each with a zone captain
- ~100 active riders, ~200 merchants
- Monthly targets: 400 orders/rider, ₦600k revenue/bike

COMPENSATION TIERS (riders):
- Tier 1 (0-199 orders): ₦80k base
- Tier 2 (200-299 orders): ₦100k base
- Tier 3 (300-399 orders): ₦130k base
- Tier 4 (400+ orders): ₦160k base + full commission

INSTRUCTIONS:
- Use the available tools to fetch real data before answering. Do NOT guess numbers.
- When asked about a specific person/zone/vertical, fetch their data first.
- For comparison questions, fetch data for all items being compared.
- Present numbers clearly: use ₦ for naira, format large numbers with commas.
- When suggesting actions, be specific (e.g., "Move Rider X from Zone A to Zone B" not "consider rebalancing").
- If data is unavailable or an error occurs, say so honestly.
- The current analysis period is: {period}.
- Keep responses concise but complete. Use bullet points for lists.
"""


class CoachChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        messages = request.data.get("messages", [])
        period = request.data.get("period", "this_month")

        if not messages:
            return Response({"error": "messages is required"}, status=400)

        # Validate message format
        for msg in messages:
            if msg.get("role") not in ("user", "assistant"):
                return Response(
                    {"error": "Each message must have role 'user' or 'assistant'"},
                    status=400,
                )
            if not msg.get("content"):
                return Response(
                    {"error": "Each message must have non-empty content"},
                    status=400,
                )

        system = SYSTEM_PROMPT.format(period=period)
        provider = get_provider()

        try:
            result = provider.chat(
                system=system,
                messages=messages,
                tools=TOOLS,
                tool_executor=execute_tool,
                max_rounds=6,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Coach LLM API error: %s", exc)
            if exc.response.status_code == 429:
                return Response(
                    {"error": "AI service is rate-limited. Please wait a moment and try again."},
                    status=429,
                )
            return Response(
                {"error": f"AI service error ({exc.response.status_code})"},
                status=502,
            )
        except Exception as exc:
            logger.exception("Coach chat error")
            return Response(
                {"error": f"AI service error: {str(exc)[:200]}"},
                status=502,
            )

        return Response({
            "reply": result["reply"],
            "tool_calls": result["tool_calls"],
        })
