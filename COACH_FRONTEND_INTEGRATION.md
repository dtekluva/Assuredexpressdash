# APEX AI Coach — Frontend Integration Guide

The backend now has a fully functional AI Coach endpoint that replaces the direct Anthropic API call in `CoachPage.jsx`. The coach uses **tool-calling** to fetch real operations data on demand, so it can answer any question with actual numbers.

---

## Backend Endpoint

```
POST /api/v1/coach/chat/
```

**Auth:** JWT Bearer token (same as all other endpoints)

### Request Body

```json
{
  "messages": [
    { "role": "user", "content": "Which riders are underperforming?" },
    { "role": "assistant", "content": "Based on the data..." },
    { "role": "user", "content": "Focus on Ikeja zone" }
  ],
  "period": "this_month"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | array | Yes | Full conversation history. Each item has `role` (`"user"` or `"assistant"`) and `content` (string). |
| `period` | string | No | Period filter passed to data tools. Defaults to `"this_month"`. Valid values: `today`, `yesterday`, `this_week`, `past_7_days`, `this_month`, `last_month`, `this_year` |

### Response (200 OK)

```json
{
  "reply": "Here are the underperforming riders in Ikeja zone:\n\n- **Chidi Okafor**: 142 orders (35% of target)...",
  "tool_calls": [
    { "name": "get_zone_riders", "input": { "zone_id": "ikeja-001", "period": "this_month" } },
    { "name": "get_zone_dashboard", "input": { "zone_id": "ikeja-001", "period": "this_month" } }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reply` | string | The AI's text response (may contain markdown) |
| `tool_calls` | array | Which data tools the AI called to answer the question (for transparency/debugging — optional to display) |

### Error Responses

- **400** — `{ "error": "messages is required" }` or `{ "error": "Each message must have role 'user' or 'assistant'" }`
- **401** — JWT auth failed
- **502** — `{ "error": "AI service error: ..." }` (Anthropic/OpenAI API down or misconfigured)

---

## What to Change in `CoachPage.jsx`

### 1. Add endpoint to `endpoints.js`

```js
// ── Coach (AI) ───────────────────────────────────────────────────────────────
export const coachChat = (messages, period) =>
  client.post("/coach/chat/", { messages, period }).then((r) => r.data);
```

### 2. Update `CoachPage.jsx`

**Remove:**
- The `systemContext` variable (entire block from line ~27 to ~47) — the backend handles the system prompt now
- The direct `fetch("https://api.anthropic.com/v1/messages", ...)` call

**Replace `sendMessage` with:**

```jsx
import { coachChat } from "@/api/endpoints";

// Inside the component, get period from context:
const { period, periodLabel } = usePeriod();

const sendMessage = async (text) => {
  const userMsg = text || input.trim();
  if (!userMsg) return;
  setInput("");
  const newMsgs = [...msgs, { role: "user", content: userMsg }];
  setMsgs(newMsgs);
  setLoading(true);

  try {
    const data = await coachChat(
      newMsgs.map((m) => ({ role: m.role, content: m.content })),
      period,
    );
    setMsgs((prev) => [...prev, { role: "assistant", content: data.reply }]);
  } catch (err) {
    const detail = err.response?.data?.error || "Unable to connect to APEX. Check your connection.";
    setMsgs((prev) => [...prev, { role: "assistant", content: `⚠️ ${detail}` }]);
  } finally {
    setLoading(false);
  }
};
```

### 3. Increase timeout (recommended)

The coach may take 5-15 seconds because it runs multiple tool calls (fetching data from the main backend) before responding. Either:
- Increase the axios client timeout for coach calls specifically, OR
- Use a separate axios instance for coach with `timeout: 60_000`

### 4. Optional: render markdown

The coach's `reply` may contain **bold**, bullet points, tables, etc. Consider rendering with a markdown library (e.g., `react-markdown`) for better formatting.

### 5. Optional: show tool calls

The response includes `tool_calls` — you could show a small "Sources" or "Data fetched" indicator:

```
🔍 Fetched: zone riders (Ikeja), zone dashboard (Ikeja)
```

This adds transparency so users know the AI is pulling real data.

---

## Suggested Updated Suggestions

The old suggestions were generic. With tool-calling, the coach can handle much more specific questions:

```js
const SUGGESTIONS = [
  "Who has ghost-ride anomalies?",
  "Which merchants need reactivation urgently?",
  "Riders with low acceptance rates this period",
  "How to boost Erinfolami's merchant activation?",
  "Calculate earnings gap across all verticals",
  "What's the best approach to hit this month's targets?",
];
```

---

## Available Tools (what the AI can fetch)

The backend gives the AI access to 13 data tools. The AI decides which to call based on the user's question:

| Tool | What it fetches |
|------|----------------|
| `get_dashboard_summary` | Top-level KPIs: orders, revenue, activation rate, flags |
| `list_verticals` | All verticals with performance summaries |
| `get_vertical_detail` | Single vertical: zones, riders, merchants, targets |
| `get_zone_dashboard` | Single zone: orders, revenue, targets, completion rates |
| `get_zone_riders` | All riders in a zone with individual metrics |
| `get_zone_merchants` | All merchants in a zone with status and revenue |
| `get_rider_performance` | Single rider: orders, acceptance rate, ghost rides, salary tier |
| `get_merchant_analytics` | Single merchant: order volume, revenue, activation status |
| `get_leaderboard` | Zone leaderboard ranked by performance |
| `get_order_analytics` | Order totals, completion rates, trends (filterable by zone/vertical) |
| `list_zones` | All zones with basic info (for finding zone IDs) |
| `list_riders` | All riders, optionally filtered by zone |
| `list_merchants` | All merchants, optionally filtered by zone |

The AI can chain multiple tools in a single turn. For example, "Compare Ikeja and Surulere" would call `get_zone_dashboard` twice.

---

## Notes

- **No API keys on the frontend** — the backend handles all LLM communication
- **Provider-agnostic** — backend can switch between Anthropic (Claude) and OpenAI (GPT) via env var. The frontend doesn't need to know or care
- **Conversation history** — send the full `messages` array each time (the backend doesn't store state between requests)
- **Period-aware** — pass the current period so the AI queries data for the right timeframe
