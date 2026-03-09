# Assured Express — DigitalOcean Droplet Deployment Guide

Deploy the Assured Express Operations Dashboard on a single DigitalOcean (DO) droplet
running Ubuntu 24.04, with Nginx, PostgreSQL 16, Redis 7, Gunicorn + Uvicorn workers,
Celery, and Let's Encrypt SSL.

---

## Prerequisites

| Item | Details |
|------|---------|
| DO Droplet | Ubuntu 24.04, minimum **2 GB RAM / 1 vCPU** (recommended 4 GB for Celery) |
| Domain | A domain (e.g. `api.assuredexpress.ng`) with an **A record** pointing to the droplet's IP |
| SSH access | Root or sudo user on the droplet |
| Local machine | The project repo at `/home/ibejih/projects/ae_project` |

---

## 1. Initial Server Setup

SSH into your droplet:

```bash
ssh root@YOUR_SERVER_IP
```

### 1.1 Create a deploy user

```bash
adduser deploy
usermod -aG sudo deploy
```

### 1.2 Set up SSH key for the deploy user

```bash
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

### 1.3 Update the system

```bash
apt update && apt upgrade -y
```

### 1.4 Set the timezone

```bash
timedatectl set-timezone Africa/Lagos
```

### 1.5 Configure the firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Now switch to the deploy user for the rest of the guide:

```bash
su - deploy
```

---

## 2. Install System Dependencies

```bash
sudo apt install -y \
  python3.12 python3.12-venv python3.12-dev \
  build-essential libpq-dev \
  postgresql-16 postgresql-contrib-16 \
  redis-server \
  nginx \
  certbot python3-certbot-nginx \
  git curl supervisor
```

> If `python3.12` is not available in the default repos, add the deadsnakes PPA first:
> ```bash
> sudo add-apt-repository ppa:deadsnakes/ppa -y
> sudo apt update
> sudo apt install -y python3.12 python3.12-venv python3.12-dev
> ```

---

## 3. Configure PostgreSQL

### 3.1 Create the database and user

```bash
sudo -u postgres psql
```

Inside the PostgreSQL shell:

```sql
CREATE USER ae_user WITH PASSWORD 'CHOOSE_A_STRONG_PASSWORD';
CREATE DATABASE assured_express OWNER ae_user;
ALTER USER ae_user CREATEDB;  -- needed if you want to run tests on the server
\q
```

### 3.2 Verify the connection

```bash
psql -U ae_user -d assured_express -h localhost
# Enter the password when prompted. If you see the psql prompt, it works.
\q
```

> If peer authentication fails, edit `/etc/postgresql/16/main/pg_hba.conf` and change
> the line for `local all all` from `peer` to `md5`, then restart:
> ```bash
> sudo systemctl restart postgresql
> ```

---

## 4. Configure Redis

Redis should already be running after install. Verify:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
# Expected: PONG
```

---

## 5. Deploy the Application Code

### 5.1 Create the project directory

```bash
sudo mkdir -p /opt/assured_express
sudo chown deploy:deploy /opt/assured_express
```

### 5.2 Copy the code to the server

**From your local machine**, run:

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  /home/ibejih/projects/ae_project/backend/ \
  deploy@YOUR_SERVER_IP:/opt/assured_express/
```

### 5.3 Set up the Python virtual environment

Back on the server:

```bash
cd /opt/assured_express
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # production ASGI server wrapper
```

---

## 6. Configure Environment Variables

Create the production `.env` file:

```bash
nano /opt/assured_express/.env
```

Paste and edit the following:

```ini
# ──── Core ────
SECRET_KEY=GENERATE_A_LONG_RANDOM_STRING_HERE
DEBUG=False
ALLOWED_HOSTS=api.assuredexpress.ng,YOUR_SERVER_IP

# ──── Database ────
DB_NAME=assured_express
DB_USER=ae_user
DB_PASSWORD=CHOOSE_A_STRONG_PASSWORD
DB_HOST=localhost
DB_PORT=5432

# ──── Redis ────
REDIS_URL=redis://127.0.0.1:6379/0

# ──── CORS ────
CORS_ALLOWED_ORIGINS=https://yourfrontend.com,https://www.yourfrontend.com

# ──── Comms (optional — fill in when ready) ────
TERMII_API_KEY=
TERMII_SENDER_ID=AssuredExp
SENDGRID_API_KEY=
DEFAULT_FROM_EMAIL=ops@assuredexpress.ng
FIREBASE_CREDENTIALS_JSON=
```

Generate a strong secret key:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Secure the file:

```bash
chmod 600 /opt/assured_express/.env
```

---

## 7. Run Migrations and Collect Static Files

```bash
cd /opt/assured_express
source venv/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # create your real admin account
```

> Only run `python manage.py seed_data` if you want demo data on the server.

---

## 8. Set Up Gunicorn (ASGI with Uvicorn Workers)

### 8.1 Test that Gunicorn starts

```bash
cd /opt/assured_express
source venv/bin/activate
gunicorn assured_express.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 3
```

Visit `http://YOUR_SERVER_IP:8000/api/docs/` — you should see the Swagger page.
Press `Ctrl+C` to stop.

### 8.2 Create a systemd service

```bash
sudo nano /etc/systemd/system/assuredexpress.service
```

Paste:

```ini
[Unit]
Description=Assured Express Django ASGI Server
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/assured_express
EnvironmentFile=/opt/assured_express/.env
ExecStart=/opt/assured_express/venv/bin/gunicorn \
  assured_express.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind unix:/opt/assured_express/gunicorn.sock \
  --workers 3 \
  --timeout 120 \
  --access-logfile /opt/assured_express/logs/access.log \
  --error-logfile /opt/assured_express/logs/error.log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Create the logs directory and enable the service:

```bash
mkdir -p /opt/assured_express/logs
sudo systemctl daemon-reload
sudo systemctl enable assuredexpress
sudo systemctl start assuredexpress
sudo systemctl status assuredexpress
```

---

## 9. Set Up Celery Worker and Beat

### 9.1 Celery Worker service

```bash
sudo nano /etc/systemd/system/celery-worker.service
```

Paste:

```ini
[Unit]
Description=Assured Express Celery Worker
After=network.target redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/assured_express
EnvironmentFile=/opt/assured_express/.env
ExecStart=/opt/assured_express/venv/bin/celery \
  -A assured_express worker \
  --loglevel=info \
  --concurrency=2 \
  --logfile=/opt/assured_express/logs/celery-worker.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 9.2 Celery Beat service (task scheduler)

```bash
sudo nano /etc/systemd/system/celery-beat.service
```

Paste:

```ini
[Unit]
Description=Assured Express Celery Beat Scheduler
After=network.target redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/assured_express
EnvironmentFile=/opt/assured_express/.env
ExecStart=/opt/assured_express/venv/bin/celery \
  -A assured_express beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --logfile=/opt/assured_express/logs/celery-beat.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 9.3 Enable and start both services

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
sudo systemctl status celery-worker celery-beat
```

---

## 10. Configure Nginx

### 10.1 Create the Nginx site config

```bash
sudo nano /etc/nginx/sites-available/assuredexpress
```

Paste:

```nginx
upstream asgi_server {
    server unix:/opt/assured_express/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name api.assuredexpress.ng;  # <-- CHANGE to your domain

    client_max_body_size 10M;

    # ── Static files (served by Nginx, not Django) ──
    location /static/ {
        alias /opt/assured_express/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # ── Media uploads ──
    location /media/ {
        alias /opt/assured_express/media/;
        expires 7d;
    }

    # ── WebSocket connections ──
    location /ws/ {
        proxy_pass http://asgi_server;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # keep WS alive for 24h
    }

    # ── All other requests → Django ──
    location / {
        proxy_pass http://asgi_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

### 10.2 Enable the site and test

```bash
sudo ln -s /etc/nginx/sites-available/assuredexpress /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # remove default site
sudo nginx -t
sudo systemctl restart nginx
```

Visit `http://api.assuredexpress.ng/api/docs/` — you should see the Swagger UI.

---

## 11. Enable HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d api.assuredexpress.ng
```

Follow the prompts. Certbot will:
- Obtain an SSL certificate
- Automatically modify the Nginx config to redirect HTTP → HTTPS
- Set up auto-renewal

Verify auto-renewal:

```bash
sudo certbot renew --dry-run
```

After SSL is active, update your `.env`:

```ini
CORS_ALLOWED_ORIGINS=https://yourfrontend.com
```

And in `settings.py`, ensure these are set (or add to `.env` if using decouple):

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = ["https://api.assuredexpress.ng"]
```

---

## 12. Set Up Log Rotation

```bash
sudo nano /etc/logrotate.d/assuredexpress
```

Paste:

```
/opt/assured_express/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
}
```

---

## 13. Set Up Celery Beat Scheduled Tasks

After the server is running, log in to Django Admin at `https://api.assuredexpress.ng/admin/`
and navigate to **Django Celery Beat > Periodic Tasks**. Create these schedules:

| Task Name | Task | Schedule |
|-----------|------|----------|
| Nightly Aggregation | `apps.core.tasks.run_nightly_aggregation` | Crontab: `0 1 * * *` (01:00 daily) |
| Refresh Merchant Status | `apps.core.tasks.refresh_merchant_status` | Crontab: `0 2 * * *` (02:00 daily) |
| Zone Leaderboard Push | `apps.core.tasks.push_zone_leaderboard_update` | Interval: every 15 minutes |

> Alternatively, if the tasks are already registered via `CELERY_BEAT_SCHEDULE` in settings.py, they will run automatically and you can skip this step.

---

## 14. Deployment Checklist

Run through this list before going live:

- [ ] `DEBUG=False` in `.env`
- [ ] `SECRET_KEY` is a newly generated strong random string
- [ ] `ALLOWED_HOSTS` contains only your domain and server IP
- [ ] `CORS_ALLOWED_ORIGINS` lists only your frontend domain(s)
- [ ] Database password is strong and unique
- [ ] `.env` file permissions are `600` (owner read/write only)
- [ ] `python manage.py check --deploy` passes with no critical issues
- [ ] SSL certificate is installed and HTTP redirects to HTTPS
- [ ] Static files are collected (`/opt/assured_express/staticfiles/` is populated)
- [ ] All 4 services are running: `assuredexpress`, `celery-worker`, `celery-beat`, `nginx`
- [ ] Firewall only allows ports 22, 80, 443
- [ ] WebSocket connections work at `wss://api.assuredexpress.ng/ws/dashboard/`
- [ ] Superuser account is created (not the default `admin/admin123`)
- [ ] Log rotation is configured

---

## 15. Useful Commands Reference

### Service management

```bash
# Restart everything after a code update
sudo systemctl restart assuredexpress celery-worker celery-beat

# Check service status
sudo systemctl status assuredexpress
sudo systemctl status celery-worker
sudo systemctl status celery-beat

# View logs
tail -f /opt/assured_express/logs/error.log
tail -f /opt/assured_express/logs/celery-worker.log
journalctl -u assuredexpress -f
```

### Deploying code updates

```bash
# From your local machine
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' --exclude='.env' \
  /home/ibejih/projects/ae_project/backend/ \
  deploy@YOUR_SERVER_IP:/opt/assured_express/

# On the server
cd /opt/assured_express
source venv/bin/activate
pip install -r requirements.txt        # if dependencies changed
python manage.py migrate               # if models changed
python manage.py collectstatic --noinput  # if static files changed
sudo systemctl restart assuredexpress celery-worker celery-beat
```

### Django management

```bash
cd /opt/assured_express && source venv/bin/activate
python manage.py check --deploy        # security audit
python manage.py showmigrations        # check migration state
python manage.py dbshell               # PostgreSQL shell
python manage.py shell                 # Django shell
```

### Database backup

```bash
# Create backup
pg_dump -U ae_user -h localhost assured_express > ~/backup_$(date +%F).sql

# Restore backup
psql -U ae_user -h localhost assured_express < ~/backup_2026-02-28.sql
```

---

## 16. Optional: Automated Backups with Cron

```bash
sudo mkdir -p /opt/backups
sudo chown deploy:deploy /opt/backups
crontab -e
```

Add this line to back up the database daily at 3 AM:

```
0 3 * * * pg_dump -U ae_user -h localhost assured_express | gzip > /opt/backups/ae_$(date +\%F).sql.gz && find /opt/backups -mtime +7 -delete
```

This keeps the last 7 days of backups and automatically deletes older ones.

---

## Architecture Diagram

```
                    ┌──────────────┐
                    │   Internet   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    Nginx     │  :80/:443
                    │  (reverse    │  SSL termination
                    │   proxy)     │  static/media files
                    └──────┬───────┘
                           │ unix socket
                    ┌──────▼───────┐
                    │  Gunicorn    │  3 Uvicorn workers
                    │  (ASGI)      │  HTTP + WebSocket
                    └──┬───────┬───┘
                       │       │
              ┌────────▼──┐  ┌─▼──────────┐
              │ PostgreSQL │  │   Redis     │
              │   16       │  │   7         │
              │ (database) │  │ (cache +    │
              └────────────┘  │  broker +   │
                              │  channels)  │
                              └──────┬──────┘
                                     │
                        ┌────────────▼────────────┐
                        │  Celery Worker + Beat    │
                        │  (background tasks,      │
                        │   nightly aggregation,   │
                        │   broadcast dispatch)    │
                        └──────────────────────────┘
```
