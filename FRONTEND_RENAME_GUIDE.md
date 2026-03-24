# Frontend Implementation Guide — Hierarchy Rename

The backend has been updated to use new business terminology. The frontend needs to be updated to match.

## Terminology Mapping

| Old Term | New Term | Notes |
|----------|----------|-------|
| Vertical | **Zone** | Top-level region (A/B/C/D) |
| Vertical Lead | **Zone Lead** | Manages a zone |
| Zone | **Relay Hub** (or "Hub") | Sub-area within a zone |
| Zone Captain | **Hub Captain** | Manages a hub |
| Relay Node | **Relay Node** | Physical handoff point (NEW entity) |

---

## 1. API Endpoint Changes

All endpoints are under `/api/v1/core/`. The old paths no longer exist.

### Analytics / Dashboard

| Old Endpoint | New Endpoint |
|-------------|-------------|
| `GET /core/dashboard/` | `GET /core/dashboard/` (unchanged, but response keys changed — see below) |
| `GET /core/verticals/` | `GET /core/zones/` |
| `GET /core/verticals/:id/` | `GET /core/zones/:id/` |
| `GET /core/verticals/:id/performance/` | `GET /core/zones/:id/performance/` |
| `GET /core/zones/` | `GET /core/hubs/` |
| `GET /core/zones/:id/dashboard/` | `GET /core/hubs/:id/dashboard/` |
| `GET /core/zones/:id/performance/` | `GET /core/hubs/:id/performance/` |
| `GET /core/zones/:id/riders/` | `GET /core/hubs/:id/riders/` |
| `GET /core/zones/:id/merchants/` | `GET /core/hubs/:id/merchants/` |

### Relay Nodes (NEW)

| Endpoint | Description |
|----------|-------------|
| `GET /core/relay-nodes/` | List all relay nodes. Filter by hub: `?hub=<uuid>` |
| `GET /core/relay-nodes/:id/` | Get a single relay node |

### Riders, Merchants, Orders (unchanged paths)

| Endpoint | Change |
|----------|--------|
| `GET /core/riders/` | No path change |
| `GET /core/riders/:id/` | No path change |
| `GET /core/riders/:id/performance/` | No path change |
| `GET /core/riders/:id/orders/` | No path change |
| `GET /core/riders/locations/` | No path change |
| `GET /core/merchants/` | No path change |
| `GET /core/merchants/:id/` | No path change |
| `GET /core/merchants/:id/analytics/` | No path change |
| `GET /core/orders/` | No path change |
| `GET /core/orders/analytics/` | Query params changed (see below) |

### Leaderboard

| Old | New |
|-----|-----|
| `GET /core/leaderboard/?scope=zones` | `GET /core/leaderboard/?scope=hubs` |
| `GET /core/leaderboard/?scope=verticals` | `GET /core/leaderboard/?scope=zones` |

### Order Analytics Query Params

| Old Param | New Param |
|-----------|-----------|
| `?zone=<id>` | `?hub=<id>` |
| `?vertical=<id>` | `?zone=<id>` |

### Admin CRUD

| Old Endpoint | New Endpoint |
|-------------|-------------|
| `POST/GET /core/admin/verticals/` | `POST/GET /core/admin/zones/` |
| `GET/PATCH/DELETE /core/admin/verticals/:id/` | `GET/PATCH/DELETE /core/admin/zones/:id/` |
| `POST/GET /core/admin/zones/` | `POST/GET /core/admin/hubs/` |
| `GET/PATCH/DELETE /core/admin/zones/:id/` | `GET/PATCH/DELETE /core/admin/hubs/:id/` |
| `POST/GET /core/admin/zone-targets/` | `POST/GET /core/admin/hub-targets/` |
| `GET/PATCH/DELETE /core/admin/zone-targets/:id/` | `GET/PATCH/DELETE /core/admin/hub-targets/:id/` |

### Admin — Rider Reassignment

| Old Body | New Body |
|----------|----------|
| `{ "rider_id": "...", "new_zone_id": "..." }` | `{ "rider_id": "...", "new_hub_id": "..." }` |
| `{ "rider_ids": [...], "new_zone_id": "..." }` | `{ "rider_ids": [...], "new_hub_id": "..." }` |

**Important:** `new_hub_id` must be a **Relay Node UUID** (not a zone or hub UUID). Riders are now assigned to relay nodes. To get relay nodes for a hub, call `GET /core/relay-nodes/?hub=<hub_uuid>`.

### Auth — Signup

| Old Endpoint | New Endpoint |
|-------------|-------------|
| `GET /auth/signup-options/` | `GET /auth/signup-options/` (same path, response changed) |
| `POST /auth/signup/` | `POST /auth/signup/` (same path, body changed) |

---

## 2. Response Key Changes

### Dashboard (`GET /core/dashboard/`)

```diff
{
-  "verticals": [
+  "zones": [
     {
       "id": "...",
       "full_name": "Island & Lekki Corridor",
       "code": "A",
       "lead_name": "Dennis",
-      "zone_count": 6,
+      "hub_count": 6,
       "rider_count": 10,
       "merchant_count": 50,
       "total_orders": 1200,
       "total_revenue": 5000000,
       "pct": 85.5,
       ...
     }
   ],
   "total_orders": ...,
   "total_revenue": ...,
   ...
}
```

### Zone Detail (`GET /core/zones/:id/`)

```diff
{
-  "vertical": {
+  "zone": {
     "id": "...",
     "full_name": "Island & Lekki Corridor",
     "code": "A",
     "lead_name": "Dennis",
     "color_hex": "#10B981"
   },
-  "zones": [
+  "hubs": [
     {
       "id": "...",
       "name": "Osapa/Jakande",
       "captain": "Emeka Okafor",
       "orders": 200,
       "revenue": 800000,
       "riders": [...],
       "merchants": [...]
     }
   ],
   "total_orders": ...,
   "total_revenue": ...,
   "pct": ...
}
```

### Signup Options (`GET /auth/signup-options/`)

```diff
{
-  "verticals": [
+  "zones": [
     { "id": "...", "name": "Island & Lekki Corridor", "lead_name": "Dennis" }
   ],
-  "zones": [
+  "hubs": [
-    { "id": "...", "name": "Osapa/Jakande", "vertical_id": "..." }
+    { "id": "...", "name": "Osapa/Jakande", "zone_id": "..." }
   ]
}
```

### Signup Body (`POST /auth/signup/`)

```diff
{
   "first_name": "...",
   "last_name": "...",
   "email": "...",
   "phone": "...",
   "password": "...",
-  "role": "vertical_lead",      // or "zone_captain"
+  "role": "zone_lead",          // or "hub_captain"
-  "vertical": "<uuid>",
+  "zone": "<uuid>",
-  "zone": "<uuid>",             // for zone_captain
+  "hub": "<uuid>",              // for hub_captain
}
```

### User Profile / JWT Token

```diff
{
-  "vertical": "<zone_uuid>",
-  "vertical_name": "Island & Lekki Corridor",
-  "zone": "<hub_uuid>",
-  "zone_name": "Osapa/Jakande",
+  "zone": "<zone_uuid>",
+  "zone_name": "Island & Lekki Corridor",
+  "hub": "<hub_uuid>",
+  "hub_name": "Osapa/Jakande",
-  "role": "vertical_lead"       // or "zone_captain"
+  "role": "zone_lead"           // or "hub_captain"
}
```

### JWT Token Claims

```diff
{
-  "role": "vertical_lead",
+  "role": "zone_lead",
-  "vertical": "<zone_uuid>",
+  "zone": "<zone_uuid>",
-  "zone": "<hub_uuid>",
+  "hub": "<hub_uuid>",
}
```

---

## 3. UI Label Changes (Search & Replace)

### Display Text

| Search For | Replace With |
|-----------|-------------|
| `Vertical Lead` | `Zone Lead` |
| `Vertical Leads` | `Zone Leads` |
| `VERTICAL LEADS` | `ZONE LEADS` |
| `Zone Captain` | `Hub Captain` |
| `Zone Captains` | `Hub Captains` |
| `ZONE CAPTAIN` | `HUB CAPTAIN` |
| `Manage Verticals` | `Manage Zones` |
| `Manage Zones` | `Manage Hubs` |
| `New Vertical` | `New Zone` |
| `New Zone` | `New Hub` |
| `All Verticals` | `All Zones` |
| `Zone Board` | `Hub Board` |
| `ZONE BOARD` | `HUB BOARD` |
| `Zone Targets` | `Hub Targets` |

**Important:** Do these replacements carefully and in the right order to avoid double-replacing. For example, rename "Vertical" → "Zone" first, then rename old "Zone" references to "Hub" — but only the ones that referred to the OLD zone concept.

### Role Values in Code

| Search For | Replace With |
|-----------|-------------|
| `vertical_lead` | `zone_lead` |
| `zone_captain` | `hub_captain` |

### Variable / State Names

| Search For | Replace With | Context |
|-----------|-------------|---------|
| `verticals` | `zones` | API response arrays, state variables |
| `vertical` | `zone` | Single entity references, IDs |
| `verticalId` | `zoneId` | URL params, state |
| `vertical_id` | `zone_id` | API fields |
| `vertical_name` | `zone_name` | API fields |
| `zone_count` | `hub_count` | Dashboard response |
| `zones` (old zone array) | `hubs` | Zone detail response, admin page |
| `zone` (old single zone) | `hub` | Entity references |
| `zoneId` (old) | `hubId` | URL params for hub pages |
| `zone_id` (old) | `hub_id` | API fields for hub references |
| `zone_name` (old) | `hub_name` | API fields for hub |
| `new_zone_id` | `new_hub_id` | Rider reassignment body |

---

## 4. Page-by-Page Changes

### Dashboard (`/dashboard`)
- Section header: "VERTICAL LEADS" → "ZONE LEADS"
- Section header: "ZONE BOARD" → "HUB BOARD"
- Cards show zone data (was vertical data)
- Bottom board shows hubs (was zones)
- API: use `response.zones` instead of `response.verticals`
- In each zone: `zone.hub_count` instead of `zone.zone_count`

### Zone Detail Page (was Vertical Detail — `/zones/:id`)
- Header: show "ZONE LEAD" instead of "VERTICAL LEAD"
- Tabs: "Hubs" instead of "Zones", "Riders", "Merchants", "Comms"
- Link: "← All Zones" instead of "← All Verticals"
- API: `response.zone` instead of `response.vertical`, `response.hubs` instead of `response.zones`

### Admin Console — Verticals Tab → Zones Tab
- Tab label: "Zones" instead of "Verticals"
- Table header: "LEAD NAME" stays
- Button: "+ New Zone" instead of "+ New Vertical"
- API: `GET /core/admin/zones/`, `POST /core/admin/zones/`

### Admin Console — Zones Tab → Hubs Tab
- Tab label: "Hubs" instead of "Zones"
- Table: add ZONE column (parent zone), rename VERTICAL column
- Button: "+ New Hub" instead of "+ New Zone"
- API: `GET /core/admin/hubs/`, `POST /core/admin/hubs/`

### Admin Console — Zone Targets Tab → Hub Targets Tab
- Tab label: "Hub Targets" instead of "Zone Targets"
- API: `GET /core/admin/hub-targets/`, `POST /core/admin/hub-targets/`

### Signup Page
- Dropdown labels: "Zone" instead of "Vertical", "Hub" instead of "Zone"
- Role options: "Zone Lead" instead of "Vertical Lead", "Hub Captain" instead of "Zone Captain"
- API fields: see Signup Body changes above

### Navigation
- If there are any nav items referencing "Verticals" or "Zones", rename accordingly

---

## 5. New Feature — Relay Nodes (Optional)

Relay nodes are physical handoff points within hubs. They are a new entity from the AXpress API. You can optionally add a section to show them.

**Endpoint:** `GET /core/relay-nodes/?hub=<hub_uuid>`

**Response shape** (from AXpress, proxied through OCC):
```json
[
  {
    "id": "...",
    "name": "Node A",
    "zone": "<hub_uuid>",
    "zone_name": "Osapa/Jakande",
    "hub_captain_name": "Emeka",
    "hub_captain_phone": "080..."
  }
]
```

Note: The AXpress API uses `zone` and `zone_name` in the relay node response (their old naming). The OCC backend proxies this as-is.

---

## 6. Files to Update

Based on the current frontend structure (`/frontend/src/`):

| File/Dir | What to Change |
|----------|---------------|
| `api/endpoints.js` | All endpoint paths and function names |
| `components/dashboard/` | Dashboard labels, data keys |
| `components/verticals/` | Rename dir to `zones/`, update all refs |
| `components/zones/` | Rename dir to `hubs/`, update all refs |
| `context/` | State variable names |
| `hooks/` | API hook function names |
| `utils/` | Any formatters referencing old names |

---

## 7. Migration Strategy

Recommended approach:
1. Update `api/endpoints.js` first — change all paths and function names
2. Update state/context stores
3. Update components page by page
4. Test each page after updating
5. Deploy frontend and backend together (old endpoints no longer exist)
