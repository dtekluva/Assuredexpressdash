# Assured Express — Operations Command Center

Full-stack operations dashboard for Assured Express Logistics, Lagos.
Real-time rider performance, merchant tracking, and multi-channel communications.

```
ae_project/
├── backend/                  Django 5 · DRF · PostgreSQL · Redis · Celery · WebSockets
├── frontend/                 React 18 · Vite · TanStack Query · React Router
└── docker-compose.yml        Backend-only Docker startup (db + redis + api)
```

---

## Stack at a Glance

| Layer | Technology |
|---|---|
| API | Django 5 + Django REST Framework |
| Auth | JWT (SimpleJWT) with token rotation |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 |
| Background tasks | Celery + Celery Beat |
| Real-time | Django Channels (WebSocket) |
| SMS / WhatsApp | Termii (Nigerian gateway) |
| Email | SendGrid |
| Push notifications | Firebase Cloud Messaging |
| Frontend | React 18 + Vite |
| State / Data | TanStack Query v5 + Zustand |
| API docs | drf-spectacular (Swagger + Redoc) |

---

## Quick Start (Backend Docker + Frontend npm)

```bash
# 1. Clone and enter
git clone <repo-url> && cd ae_project

# 2. Create backend env file
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum fill in SECRET_KEY

# 3. Create frontend env file
cp frontend/.env.example frontend/.env
# Set:
#   VITE_API_URL=http://localhost:18000/api/v1
#   VITE_WS_URL=ws://localhost:18000/ws

# 4. Start backend services only (db + redis + django api)
docker compose up -d --build

# 5. Check backend
curl -i http://localhost:18000/api/v1/auth/login/
# Expected: 405 Method Not Allowed (endpoint exists; it only accepts POST)

# 6. Start frontend with npm (no Docker)
cd frontend
npm install
npm run dev
```

The `backend` service automatically runs:
1. `python manage.py migrate`
2. `python manage.py seed_data` — creates 4 verticals, 20 zones, 100 riders, 200 merchants, 6 months of synthetic snapshots

Endpoints in this setup:
- Frontend: `http://localhost:3000` (or `3001` if Vite selects next free port)
- Backend API: `http://localhost:18000`
- Swagger: `http://localhost:18000/api/docs/`
- Admin: `http://localhost:18000/admin/` (`admin / admin123`)

Useful commands:

```bash
docker compose logs -f backend
docker compose down
```

---

## Local Development (Without Docker)

### Backend

```bash
cd backend

# Create virtual env
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL and Redis details

# Database setup
createdb assured_express            # or use psql
python manage.py migrate
python manage.py seed_data

# Start Django dev server (HTTP)
python manage.py runserver

# Start Uvicorn for WebSocket support
uvicorn assured_express.asgi:application --reload --port 8000

# In separate terminals:
celery -A assured_express worker -l info          # background tasks
celery -A assured_express beat -l info             # scheduled tasks
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                         # http://localhost:3000
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DEBUG` | — | `True` in dev, `False` in prod |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | ✅ | PostgreSQL connection |
| `REDIS_URL` | ✅ | Redis connection string |
| `CORS_ALLOWED_ORIGINS` | ✅ | Comma-separated frontend origins |
| `TERMII_API_KEY` | SMS/WA | [termii.com](https://termii.com) — Nigerian gateway |
| `TERMII_SENDER_ID` | SMS/WA | Your registered sender name |
| `SENDGRID_API_KEY` | Email | SendGrid API key |
| `DEFAULT_FROM_EMAIL` | Email | `ops@yourdomain.ng` |
| `FIREBASE_CREDENTIALS_JSON` | Push | Firebase service account JSON (single line) |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Django API base URL (e.g. `http://localhost:18000/api/v1`) |
| `VITE_WS_URL` | WebSocket base URL (e.g. `ws://localhost:18000/ws`) |

---

## API Reference

Full interactive docs available at:
- **Swagger UI:** `http://localhost:18000/api/docs/`
- **Redoc:** `http://localhost:18000/api/redoc/`

### Core Endpoints

```
POST   /api/v1/auth/login/                  Login → access + refresh tokens
POST   /api/v1/auth/logout/                 Blacklist refresh token
POST   /api/v1/auth/token/refresh/          Refresh access token
GET    /api/v1/auth/profile/                Current user profile
POST   /api/v1/auth/fcm-token/              Register rider push token

GET    /api/v1/core/dashboard/?period=      KPI summary (all verticals)
GET    /api/v1/core/leaderboard/?scope=     Zone or vertical ranking

GET    /api/v1/core/verticals/              List all verticals
GET    /api/v1/core/verticals/{id}/performance/?period=   Vertical deep-dive

GET    /api/v1/core/zones/?vertical={id}    Zones (filterable by vertical)
GET    /api/v1/core/zones/{id}/performance/?period=       Zone deep-dive

GET    /api/v1/core/riders/?zone={id}       Riders (filterable by zone)
GET    /api/v1/core/riders/{id}/performance/?period=      9-metric profile
GET    /api/v1/core/riders/{id}/orders/     Rider's order history

GET    /api/v1/core/merchants/?zone={id}    Merchants (filterable)
GET    /api/v1/core/merchants/{id}/performance/?period=   Merchant metrics

GET    /api/v1/core/orders/                 Orders (filterable by status/zone/rider)
POST   /api/v1/core/orders/                 Create order
POST   /api/v1/core/orders/{id}/assign/     Assign rider

GET    /api/v1/comms/templates/             Message templates
POST   /api/v1/comms/broadcasts/            Create broadcast
POST   /api/v1/comms/broadcasts/{id}/send/  Dispatch broadcast
GET    /api/v1/comms/broadcasts/{id}/deliveries/  Per-recipient delivery status

GET    /api/v1/comms/notifications/         Rider's in-app notifications
POST   /api/v1/comms/notifications/{id}/read/  Mark as read
```

### Period Query Parameter

All performance endpoints accept `?period=` and optionally `?custom_month=`:

| Value | Description |
|---|---|
| `today` | Current day only |
| `yesterday` | Previous day |
| `this_week` | Monday to today |
| `past_7` | Rolling last 7 days |
| `this_month` | Calendar month to date |
| `last_month` | Previous full month |
| `this_year` | January to today |
| `custom_month` | Specific month (0=Jan…11=Dec), pass `custom_month=0` |

### WebSocket Endpoints

```
ws://host/ws/dashboard/        Live KPI updates → all dashboard clients
ws://host/ws/zone/{zone_id}/   Live zone feed → zone captains
```

---

## User Roles & Permissions

| Role | Access |
|---|---|
| `super_admin` | Full access to all verticals, zones, riders, merchants |
| `vertical_lead` | Own vertical's data only |
| `zone_captain` | Own zone's data only |
| `ops_analyst` | Read-only access to all data |
| `rider` | Own profile + orders + in-app notifications |

JWT token payload includes `role`, `vertical`, and `zone` for front-end scoping.

---

## Data Architecture

```
Vertical (4)
  └── Zone (5 per vertical = 20 total)
        ├── Rider (5 per zone = 100 total)
        │     └── RiderSnapshot (daily performance record)
        └── Merchant (10 per zone = 200 total)
              └── MerchantSnapshot (daily order record)

Order (source of truth → feeds into Snapshots via nightly Celery task)

Broadcast → BroadcastDelivery (per-recipient delivery tracking)
         → RiderInAppNotification (rider app inbox)
```

**Snapshot strategy:** Daily snapshots are pre-computed nightly by Celery. Dashboard queries aggregate these snapshots, keeping API response times under 100ms even for complex period filters across all 100 riders.

---

## Comms Architecture

```
CommTab (React) → POST /api/v1/comms/broadcasts/
                → POST /api/v1/comms/broadcasts/{id}/send/
                     ↓
               Celery task: dispatch_broadcast
                     ↓
       ┌─────────────┬─────────────┬─────────────┐
       │             │             │             │
  send_sms()   send_whatsapp()  send_email()  send_push()
  (Termii)      (Termii WA)    (SendGrid)    (Firebase FCM)
       │             │             │             │
  BroadcastDelivery (per recipient, per channel)
  RiderInAppNotification (riders)
```

---

## Management Commands

```bash
# Seed demo data (runs automatically on Docker startup)
python manage.py seed_data
python manage.py seed_data --months 12   # 12 months of history
python manage.py seed_data --clear       # wipe and re-seed

# Create a new superuser
python manage.py createsuperuser

# Generate fresh API schema
python manage.py spectacular --file schema.yaml
```

---

## Demo Credentials

| Role | Username | Password |
|---|---|---|
| Super Admin | `admin` | `admin123` |
| Vertical Lead | `lead_dennis` | `demo1234` |
| Zone Captain | `captain_dennis-awoyaya` | `demo1234` |

---

## Project Structure

```
backend/
├── assured_express/
│   ├── settings.py         All configuration
│   ├── urls.py             URL routing
│   ├── asgi.py             ASGI + WebSocket routing
│   └── celery.py           Celery app
├── apps/
│   ├── authentication/
│   │   ├── models.py       Custom User model with roles
│   │   ├── views.py        Login, logout, profile, FCM token
│   │   └── urls.py
│   ├── core/
│   │   ├── models.py       Vertical, Zone, Rider, Merchant, Order, Snapshots
│   │   ├── serializers.py  Period parsing + all serializers
│   │   ├── services.py     Metric computation (compute_rider_metrics etc.)
│   │   ├── views.py        All dashboard API endpoints
│   │   ├── permissions.py  Role-based access control
│   │   ├── consumers.py    WebSocket consumers
│   │   ├── routing.py      WS URL routing
│   │   ├── signals.py      Auto-update merchant last_order_at
│   │   ├── admin.py
│   │   └── management/commands/seed_data.py
│   └── comms/
│       ├── models.py       MessageTemplate, Broadcast, BroadcastDelivery, RiderInAppNotification
│       ├── serializers.py
│       ├── views.py        Broadcast CRUD + send + rider notifications
│       ├── services.py     Termii / SendGrid / Firebase delivery
│       ├── tasks.py        Celery: dispatch_broadcast → send_to_merchant / send_to_rider
│       └── urls.py
└── requirements.txt



---

## Postman/Newman in CI

The project includes:
- `postman/AssuredExpress_Full_API.postman_collection.json`
- `postman/AssuredExpress_Local.postman_environment.json`

Run locally:

```bash
make postman-test
```

Run against Docker backend (`http://localhost:18000`):

```bash
make postman-test-docker
```

Override credentials/base URL (useful for CI):

```bash
BASE_URL=http://127.0.0.1:8000 \
USERNAME=admin \
PASSWORD=admin123 \
RIDER_USERNAME=rider_user \
RIDER_PASSWORD=strongpass99 \
make postman-test
```

If Newman is missing:

```bash
npm install -g newman
```

---

## Production Deployment Notes

1. Set `DEBUG=False` and a strong `SECRET_KEY`
2. Use Gunicorn + Uvicorn workers for ASGI: `gunicorn assured_express.asgi:application -k uvicorn.workers.UvicornWorker`
3. Serve static files via WhiteNoise (already configured) or CDN
4. Use managed PostgreSQL and Redis (e.g. Railway, Render, AWS RDS)
5. Set `CORS_ALLOWED_ORIGINS` to your production frontend domain
6. Configure Celery Beat to run nightly snapshot aggregation tasks
7. Store `FIREBASE_CREDENTIALS_JSON` as a secret, not in `.env` files

---

## License

Internal — Assured Express Logistics © 2025
