# OCC Backend — API Endpoint Reference

> **Date:** 2026-03-09
> **Purpose:** Complete reference of all backend endpoints, their URL paths, query parameters, and response shapes. Hand this to the frontend developer.

---

## Important: What Changed

The backend views were refactored from local-DB queries to proxy calls to the main AXpress backend. This changed some URL paths and removed some CRUD endpoints. The table below maps every frontend call to what the backend now serves.

### Endpoint Migration Map

| Frontend Call (endpoints.js) | Old Path | New Path | Status |
|------------------------------|----------|----------|--------|
| `getDashboard(params)` | `GET /core/dashboard/` | `GET /core/dashboard/` | **Unchanged** |
| `getLeaderboard(params)` | `GET /core/leaderboard/` | `GET /core/leaderboard/` | **Unchanged** |
| `getVerticals()` | `GET /core/verticals/` | `GET /core/verticals/` | **Changed** — was paginated ViewSet, now flat proxy |
| `getVerticalPerformance(id)` | `GET /core/verticals/:id/performance/` | `GET /core/verticals/:id/` | **Path changed** — `/performance/` removed |
| `getZones(params)` | `GET /core/zones/` | — | **Removed** — no zone list endpoint |
| `getZonePerformance(id)` | `GET /core/zones/:id/performance/` | `GET /core/zones/:id/dashboard/` | **Path changed** — `/performance/` → `/dashboard/` |
| `getRiders(params)` | `GET /core/riders/` | — | **Removed** — no rider list endpoint |
| `getRider(id)` | `GET /core/riders/:id/` | — | **Removed** — no rider detail endpoint |
| `getRiderPerformance(id)` | `GET /core/riders/:id/performance/` | `GET /core/riders/:id/performance/` | **Unchanged** |
| `getRiderOrders(id)` | `GET /core/riders/:id/orders/` | — | **Removed** |
| `createRider(data)` | `POST /core/riders/` | — | **Removed** |
| `updateRider(id, data)` | `PATCH /core/riders/:id/` | — | **Removed** |
| `getMerchants(params)` | `GET /core/merchants/` | — | **Removed** — no merchant list endpoint |
| `getMerchant(id)` | `GET /core/merchants/:id/` | — | **Removed** — no merchant detail endpoint |
| `getMerchantPerformance(id)` | `GET /core/merchants/:id/performance/` | `GET /core/merchants/:id/analytics/` | **Path changed** — `/performance/` → `/analytics/` |
| `createMerchant(data)` | `POST /core/merchants/` | — | **Removed** |
| `updateMerchant(id, data)` | `PATCH /core/merchants/:id/` | — | **Removed** |
| `getOrders(params)` | `GET /core/orders/` | — | **Removed** — replaced by analytics |
| `createOrder(data)` | `POST /core/orders/` | — | **Removed** |
| `assignOrder(id, rider_id)` | `POST /core/orders/:id/assign/` | — | **Removed** |
| `updateOrderStatus(id, data)` | `PATCH /core/orders/:id/` | — | **Removed** |

### New Endpoints (not in original frontend)

| New Path | Purpose |
|----------|---------|
| `GET /core/zones/:id/riders/` | Zone riders with metrics (was embedded in zone performance) |
| `GET /core/zones/:id/merchants/` | Zone merchants with metrics (was embedded in zone performance) |
| `GET /core/riders/locations/` | Bulk GPS for map view |
| `GET /core/orders/analytics/` | Aggregated order analytics |

### Comms Endpoints — Unchanged

All `/comms/*` endpoints are **completely unchanged**. No path or response changes.

---

## Frontend Changes Required

Update `frontend/src/api/endpoints.js` with the following path changes:

```js
// BEFORE → AFTER

// getVerticalPerformance
client.get(`/core/verticals/${id}/performance/`, { params })
// →
client.get(`/core/verticals/${id}/`, { params })

// getZonePerformance
client.get(`/core/zones/${id}/performance/`, { params })
// →
client.get(`/core/zones/${id}/dashboard/`, { params })

// getMerchantPerformance
client.get(`/core/merchants/${id}/performance/`, { params })
// →
client.get(`/core/merchants/${id}/analytics/`, { params })
```

Remove or stub these calls (backend no longer serves them):
- `getZones`, `getRiders`, `getRider`, `getRiderOrders`
- `createRider`, `updateRider`, `createMerchant`, `updateMerchant`
- `getOrders`, `createOrder`, `assignOrder`, `updateOrderStatus`
- `getMerchants`, `getMerchant`

---

## Endpoint Response Schemas

### Query Parameters (applies to ALL core endpoints)

Every endpoint accepts:

| Param | Type | Default | Values |
|-------|------|---------|--------|
| `period` | string | `this_month` | `today`, `yesterday`, `this_week`, `past_7`, `this_month`, `last_month`, `this_year`, `custom_month` |
| `custom_month` | int | — | Month number (0–11), only used when `period=custom_month` |

---

### 1. Dashboard Summary

```
GET /api/v1/core/dashboard/?period=this_month
```

**Used by:** `DashboardPage.jsx` via `useDashboard()`

```jsonc
{
  "period": {
    "start": "2026-03-01",            // date string YYYY-MM-DD
    "end": "2026-03-09"
  },
  "total_orders": 4521,               // int — all completed orders in period
  "total_revenue": 12450000,           // int — gross revenue in naira
  "open_flags": 7,                     // int — riders with ghost-ride flags
  "active_riders": 68,                 // int
  "active_merchants": 89,              // int — merchants with status="active"
  "total_merchants": 112,              // int
  "merchant_orders": 3200,             // int — orders placed by merchants
  "merchant_revenue": 9800000,         // int
  "activation_rate": 79,               // int — percentage (active/total × 100)
  "verticals": [                       // array — one per vertical, sorted by backend
    {
      "id": 1,                         // int
      "name": "Island & Lekki",        // string — short name
      "full_name": "Dennis — Island & Lekki",  // string — includes lead name
      "color": "#3B82F6",              // string — hex colour
      "total_orders": 1200,            // int
      "total_revenue": 3600000,        // int
      "target_orders": 2000,           // int — sum of zone targets for this vertical
      "pct": 60                        // int — (total_orders / target_orders) × 100
    }
  ]
}
```

**Fields consumed by DashboardPage:**
- `dash.total_orders`, `dash.total_revenue`, `dash.open_flags`
- `dash.active_merchants`, `dash.total_merchants`, `dash.activation_rate`
- `dash.verticals[]` → `.id`, `.full_name`, `.color`, `.total_orders`, `.total_revenue`, `.target_orders`, `.pct`

---

### 2. Leaderboard

```
GET /api/v1/core/leaderboard/?period=this_month&scope=zones
```

**Used by:** `DashboardPage.jsx` via `useLeaderboard("zones")`

#### scope=zones (default)

```jsonc
[
  {
    "id": 5,                           // int — zone ID
    "name": "Ajah",                    // string
    "vertical": "Island & Lekki",      // string — vertical short name
    "color": "#3B82F6",                // string — vertical colour
    "orders": 280,                     // int
    "revenue": 840000,                 // int
    "target": 2000,                    // int — zone monthly order target
    "pct": 14                          // int — attainment percentage
  }
  // ... sorted by pct descending
]
```

**Fields consumed by DashboardPage:** `.id`, `.name`, `.vertical`, `.color`, `.pct`

**Note:** The frontend also accesses `z.vertical_id` for navigation (`/vertical/${z.vertical_id}/zone/${z.id}`). This field is **NOT** in the current response. Either:
- Add `"vertical_id": 1` to the response, OR
- The frontend falls back via `z.vertical_id ?? ""` (navigates to `/vertical//zone/5` — broken link)

#### scope=verticals

```jsonc
[
  {
    "id": 1,
    "name": "Dennis — Island & Lekki", // string — full_name
    "color": "#3B82F6",
    "orders": 1200,
    "revenue": 3600000,
    "target": 10000,
    "pct": 12
  }
]
```

---

### 3. Vertical Detail (was `/performance/`)

```
GET /api/v1/core/verticals/:id/?period=this_month
```

**Used by:** `VerticalPage.jsx` via `useVerticalPerformance(id)`

**Frontend currently calls:** `/core/verticals/${id}/performance/` — **must update to** `/core/verticals/${id}/`

```jsonc
{
  "vertical": {
    "id": 1,
    "name": "Island & Lekki",
    "full_name": "Dennis — Island & Lekki",
    "color_hex": "#3B82F6",            // NOTE: "color_hex" not "color"
    "is_active": true,
    "zone_count": 5,
    "base_pay": 250000,
    "transport_pay": 80000,
    "commission_rate": "0.0110"
  },
  "period": {
    "start": "2026-03-01",
    "end": "2026-03-09"
  },
  "total_orders": 1200,               // int
  "target_orders": 10000,             // int — sum of all zone targets in vertical
  "total_revenue": 3600000,           // int
  "pct": 12,                          // int — attainment
  "lead_pay": 369600,                 // int — base + transport + commission

  "zones": [
    {
      "id": 5,
      "name": "Ajah",
      "orders": 280,                  // int — completed orders this period
      "target": 2000,                 // int — zone order target
      "revenue": 840000,              // int
      "target_revenue": 3000000,      // int
      "perf_pct": 14,                 // int
      "flags": 2,                     // int — ghost-ride flag count
      "captain_pay": 123600,          // int

      "merchants": {                  // object — aggregate counts
        "total": 22,
        "active": 15,
        "watch": 4,
        "inactive": 3
      }
    }
  ]
}
```

**Fields consumed by VerticalPage:**
- Top level: `vertical`, `zones`, `total_orders`, `target_orders`, `total_revenue`, `pct`, `lead_pay`
- `vertical` → `.color_hex`, `.full_name`
- `zones[]` → `.id`, `.name`, `.orders`, `.target`, `.revenue`, `.perf_pct`, `.flags`, `.captain_pay`, `.merchants`
- `zones[].riders[]` — **expected by VerticalPage but NOT in current response** (see note below)
- `zones[].merchants[]` — **expected by VerticalPage but NOT in current response** (see note below)

**Critical gap:** `VerticalPage.jsx` lines 20–21 do:
```js
const allRiders    = zones.flatMap((z) => (z.riders || []).map(...));
const allMerchants = zones.flatMap((z) => (z.merchants || []).map(...));
```

The original backend embedded `riders` and `merchants` arrays inside each zone object in the vertical performance response. The new proxy must return the same structure, or the frontend rider/merchant tabs will be empty.

**Each `zones[].riders[]` item needs:**
```jsonc
{
  "id": 42,
  "full_name": "Tunde Adewale",
  "zone_name": "Ajah",                // already added by frontend
  "status": "active",
  "orders_completed": 45,
  "orders_rejected": 3,
  "orders_failed": 1,
  "revenue": 135000,
  "km_covered": 280.5,
  "online_days": 18,
  "avg_delivery_mins": 24.3,          // float or null
  "csat_avg": 4.6,                    // float or null
  "ghost_minutes": 35,
  "ghost_ratio": 8.2,                 // float — percentage
  "peak_orders": 22,
  "peak_util": 48,                    // int — percentage
  "rev_per_km": 481,                  // int
  "acceptance_rate": 94,              // int — percentage
  "failed_rate": 2.2,                 // float
  "target_orders": 154,               // int — scaled for period
  "target_revenue": 462000,           // int — scaled for period
  "pct": 29,                          // int — attainment
  "flags": [                          // array — can be empty
    {
      "type": "warning",              // "warning" | "critical"
      "msg": "High ghost-ride ratio — offline but GPS active"
    }
  ]
}
```

**Each `zones[].merchants[]` item needs:**
```jsonc
{
  "id": 88,
  "business_name": "Mama Nkechi Foods",
  "business_type": "Restaurant",
  "zone_name": "Ajah",
  "status": "active",                  // "active" | "watch" | "inactive" | "churned"
  "orders_placed": 34,
  "orders_fulfilled": 32,
  "orders_returned": 1,
  "gross_revenue": 187000,
  "avg_order_value": 5500,
  "fulfillment_rate": 94.1,           // float
  "days_since_order": 2               // int or null
}
```

---

### 4. Zone Dashboard (was `/performance/`)

```
GET /api/v1/core/zones/:id/dashboard/?period=this_month
```

**Used by:** `ZonePage.jsx` via `useZonePerformance(id)`

**Frontend currently calls:** `/core/zones/${id}/performance/` — **must update to** `/core/zones/${id}/dashboard/`

```jsonc
{
  "zone": {
    "id": 5,
    "name": "Ajah",
    "slug": "ajah",
    "vertical": 1,                     // int — vertical FK
    "vertical_name": "Island & Lekki", // string
    "is_active": true,
    "order_target": 2000,
    "revenue_target": 3000000,
    "rider_count": 5,                  // int — active riders
    "merchant_count": 22,              // int — active + watch merchants
    "base_pay": 50000,
    "transport_pay": 40000,
    "commission_rate": "0.0400"
  },
  "period": {
    "start": "2026-03-01",
    "end": "2026-03-09"
  },
  "total_orders": 280,
  "total_revenue": 840000,
  "target_orders": 2000,
  "perf_pct": 14,
  "captain_pay": 123600,

  "riders": [                          // array — same shape as vertical riders above
    {
      "id": 42,
      "full_name": "Tunde Adewale",
      "zone_name": "Ajah",
      "status": "active",
      "orders_completed": 45,
      "orders_rejected": 3,
      "orders_failed": 1,
      "revenue": 135000,
      "km_covered": 280.5,
      "online_days": 18,
      "avg_delivery_mins": 24.3,
      "csat_avg": 4.6,
      "ghost_minutes": 35,
      "ghost_ratio": 8.2,
      "peak_orders": 22,
      "peak_util": 48,
      "rev_per_km": 481,
      "acceptance_rate": 94,
      "failed_rate": 2.2,
      "target_orders": 154,
      "target_revenue": 462000,
      "pct": 29,
      "flags": []
    }
  ],

  "merchants": [                       // array — same shape as vertical merchants above
    {
      "id": 88,
      "business_name": "Mama Nkechi Foods",
      "business_type": "Restaurant",
      "zone_name": "Ajah",
      "status": "active",
      "orders_placed": 34,
      "orders_fulfilled": 32,
      "orders_returned": 1,
      "gross_revenue": 187000,
      "avg_order_value": 5500,
      "fulfillment_rate": 94.1,
      "days_since_order": 2
    }
  ],

  "merchant_stats": {                  // object — aggregate counts
    "total": 22,
    "active": 15,
    "watch": 4,
    "inactive": 3
  }
}
```

**Fields consumed by ZonePage:**
- `data.zone` → `.name`, `.vertical_name`
- `data.riders[]` → `.pct`, `.flags`, `.id`, `.full_name`, `.orders_completed`, `.target_orders`, `.acceptance_rate`, `.csat_avg`, `.online_days`, `.ghost_ratio`
- `data.merchants[]` → `.status`, `.business_name`, `.business_type`, `.id`, `.orders_placed`, `.gross_revenue`, `.avg_order_value`, `.fulfillment_rate`
- `data.total_orders`, `.target_orders`, `.perf_pct`, `.captain_pay`, `.merchant_stats`

---

### 5. Rider Performance

```
GET /api/v1/core/riders/:id/performance/?period=this_month
```

**Used by:** `RiderPage.jsx` via `useRiderPerformance(id)`

**Path: Unchanged**

```jsonc
{
  "id": 42,
  "full_name": "Tunde Adewale",
  "zone_name": "Ajah",
  "status": "active",

  // Core counts
  "orders_completed": 45,
  "orders_rejected": 3,
  "orders_failed": 1,
  "revenue": 135000,
  "km_covered": 280.5,

  // 9 performance metrics
  "online_days": 18,                   // int — days with at least 1 snapshot
  "avg_delivery_mins": 24.3,           // float or null
  "csat_avg": 4.6,                     // float or null
  "ghost_minutes": 35,                 // int
  "ghost_ratio": 8.2,                  // float — percentage
  "peak_orders": 22,                   // int
  "peak_util": 48,                     // int — percentage
  "rev_per_km": 481,                   // int — revenue ÷ km
  "acceptance_rate": 94,               // int — percentage
  "failed_rate": 2.2,                  // float — percentage

  // Targets (scaled to period)
  "target_orders": 154,
  "target_revenue": 462000,
  "pct": 29,                           // int — attainment percentage

  // Anomaly flags
  "flags": [
    {
      "type": "warning",               // "warning" | "critical"
      "msg": "High ghost-ride ratio — offline but GPS active"
    }
  ],

  // Monthly history (last 5 months) — only present in detailed view
  "order_history": [
    { "month": "Oct", "orders": 312 },
    { "month": "Nov", "orders": 356 },
    { "month": "Dec", "orders": 289 },
    { "month": "Jan", "orders": 401 },
    { "month": "Feb", "orders": 378 }
  ],
  "revenue_history": [
    { "month": "Oct", "revenue": 936000 },
    { "month": "Nov", "revenue": 1068000 },
    { "month": "Dec", "revenue": 867000 },
    { "month": "Jan", "revenue": 1203000 },
    { "month": "Feb", "revenue": 1134000 }
  ]
}
```

**Fields consumed by RiderPage:**
- All top-level fields listed above
- `rider.flags[]` → `.type`, `.msg`
- `rider.order_history[]` → `.month`, `.orders`
- `rider.revenue_history[]` → `.month`, `.revenue`

---

### 6. Merchant Analytics (was `/performance/`)

```
GET /api/v1/core/merchants/:id/analytics/?period=this_month
```

**Used by:** `useMerchantPerformance(id)` (called from merchant detail if built)

**Frontend currently calls:** `/core/merchants/${id}/performance/` — **must update to** `/core/merchants/${id}/analytics/`

```jsonc
{
  "id": 88,
  "business_name": "Mama Nkechi Foods",
  "business_type": "Restaurant",
  "zone_name": "Ajah",
  "status": "active",
  "orders_placed": 34,
  "orders_fulfilled": 32,
  "orders_returned": 1,
  "gross_revenue": 187000,
  "avg_order_value": 5500,             // int
  "fulfillment_rate": 94.1,            // float
  "days_since_order": 2,               // int or null

  // Only in detailed view
  "order_history": [
    { "month": "Oct", "orders": 28, "revenue": 154000 },
    { "month": "Nov", "orders": 31, "revenue": 170500 },
    { "month": "Dec", "orders": 22, "revenue": 121000 },
    { "month": "Jan", "orders": 38, "revenue": 209000 },
    { "month": "Feb", "orders": 34, "revenue": 187000 }
  ]
}
```

---

### 7. Rider Locations (new)

```
GET /api/v1/core/riders/locations/
```

**Not yet used by frontend.** For future map view.

```jsonc
[
  {
    "rider_id": 42,
    "name": "Tunde Adewale",
    "latitude": 6.4541,
    "longitude": 3.6218,
    "status": "online",                // "online" | "on_delivery" | "offline"
    "speed": 28.5,
    "is_moving": true,
    "last_updated": "2026-03-09T14:32:00Z",
    "zone": "Ajah"
  }
]
```

---

### 8. Order Analytics (new)

```
GET /api/v1/core/orders/analytics/?period=this_month&zone=5&vertical=1
```

**Not yet used by frontend.** For future analytics page.

```jsonc
{
  "total": 4521,
  "completed": 3890,
  "failed": 156,
  "canceled": 234,
  "pending": 241,
  "revenue": 12450000,
  "avg_delivery_fee": 2750,
  "avg_distance_km": 8.3,
  "avg_delivery_time_minutes": 26.4,
  "by_zone": [
    { "zone_id": 5, "zone_name": "Ajah", "orders": 280, "revenue": 840000 }
  ],
  "by_hour": [
    { "hour": 0, "orders": 12 },
    { "hour": 1, "orders": 5 }
    // ... 24 entries
  ]
}
```

---

### 9. Vertical List

```
GET /api/v1/core/verticals/
```

**Used by:** `useVerticals()`

**Changed:** Was a paginated DRF ViewSet (returned `{count, next, previous, results: [...]}`). Frontend already handles both formats:
```js
client.get("/core/verticals/").then((r) => r.data.results ?? r.data);
```

New response is a flat array (no pagination wrapper):

```jsonc
[
  {
    "id": 1,
    "name": "Island & Lekki",
    "full_name": "Dennis — Island & Lekki",
    "color_hex": "#3B82F6",
    "is_active": true,
    "zone_count": 5,
    "base_pay": 250000,
    "transport_pay": 80000,
    "commission_rate": "0.0110"
  }
]
```

---

## Comms Endpoints (Unchanged)

These endpoints have **zero changes** — same paths, same request/response formats.

### Templates

```
GET  /api/v1/comms/templates/?audience=merchant&msg_type=promotion
POST /api/v1/comms/templates/
```

```jsonc
// GET response (paginated)
{
  "count": 12,
  "results": [
    {
      "id": 1,
      "audience": "merchant",          // "merchant" | "rider"
      "msg_type": "promotion",         // "promotion" | "reminder" | "drip" | "seasonal" | "performance" | "incentive" | "operational" | "general"
      "label": "Flash Sale Promo",
      "subject": "Special offer for {name}!",
      "body": "Hi {name}, we have a special promotion..."
    }
  ]
}
```

### Broadcasts

```
GET  /api/v1/comms/broadcasts/?zone=5
POST /api/v1/comms/broadcasts/
POST /api/v1/comms/broadcasts/:id/send/
GET  /api/v1/comms/broadcasts/:id/deliveries/
```

```jsonc
// POST create request body
{
  "audience": "merchant",
  "zone": 5,                           // or "vertical": 1
  "recipient_filter": "active",        // "all" | "active" | "watch" | "inactive" | "critical" | "atrisk" | "flagged"
  "channels": ["whatsapp", "sms"],     // for merchants; riders always ["inapp"]
  "priority": "normal",                // "normal" | "high" | "urgent" (riders only)
  "subject": "Flash sale this weekend!",
  "body": "Hi {name}, enjoy 20% off...",
  "template": 1,                       // optional — template ID
  "scheduled_at": "2026-03-15T09:00:00Z"  // optional — omit for immediate
}

// GET list response
[
  {
    "id": 7,
    "audience": "merchant",
    "status": "sent",                  // "draft" | "scheduled" | "sending" | "sent" | "failed"
    "subject": "Flash sale this weekend!",
    "channels": ["whatsapp"],
    "sent_at": "2026-03-08T10:30:00Z",
    "total_recipients": 15,
    "open_rate": 73                    // int — percentage
  }
]
```

### Rider Notifications

```
GET  /api/v1/comms/notifications/
POST /api/v1/comms/notifications/:id/read/
```

```jsonc
// GET response
[
  {
    "id": "uuid",
    "title": "Target Alert",
    "body": "You're at 45% of your monthly target...",
    "priority": "high",
    "is_read": false,
    "read_at": null,
    "created_at": "2026-03-09T08:15:00Z"
  }
]
```

---

## Auth Endpoints (Unchanged)

```
POST /api/v1/auth/login/               → { access, refresh, user: {...} }
POST /api/v1/auth/logout/              → { detail: "Logged out" }
POST /api/v1/auth/token/refresh/       → { access }
GET  /api/v1/auth/profile/             → User object
PUT  /api/v1/auth/profile/             → Updated user object
POST /api/v1/auth/change-password/     → { detail: "Password changed" }
POST /api/v1/auth/fcm-token/           → { detail: "Token updated" }
```

---

## Summary of Required Frontend Changes

### Path updates in `endpoints.js`:

```js
// 1. Vertical performance — remove /performance/
export const getVerticalPerformance = (id, params) =>
  client.get(`/core/verticals/${id}/`, { params }).then((r) => r.data);

// 2. Zone performance — /performance/ → /dashboard/
export const getZonePerformance = (id, params) =>
  client.get(`/core/zones/${id}/dashboard/`, { params }).then((r) => r.data);

// 3. Merchant performance — /performance/ → /analytics/
export const getMerchantPerformance = (id, params) =>
  client.get(`/core/merchants/${id}/analytics/`, { params }).then((r) => r.data);
```

### Removed endpoints to handle:

These functions in `endpoints.js` will return 404. Either remove them or leave them with a `// TODO: re-add when backend supports` comment:

- `getZones`, `getRiders`, `getRider`, `getRiderOrders`
- `createRider`, `updateRider`, `createMerchant`, `updateMerchant`
- `getMerchants`, `getMerchant`
- `getOrders`, `createOrder`, `assignOrder`, `updateOrderStatus`

### Zone leaderboard navigation fix:

`DashboardPage.jsx` line 71 uses `z.vertical_id` which is not in the leaderboard response. Add `vertical_id` to the backend response or change the frontend to look it up differently.
