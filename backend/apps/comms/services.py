"""
Channel delivery services for Assured Express communications.

Providers:
  SMS / WhatsApp → Termii (https://termii.com) — Nigerian gateway
  Email          → SendGrid
  Push (In-App)  → Firebase Cloud Messaging (FCM)
"""
import json
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("apps.comms")


def personalise(body: str, context: dict) -> str:
    """Replace {tokens} in message body with context values."""
    for key, value in context.items():
        body = body.replace(f"{{{key}}}", str(value))
    return body


# ── SMS via Termii ────────────────────────────────────────────────────────────

def send_sms(phone: str, message: str) -> dict:
    """
    Send plain SMS via Termii.
    Returns {"success": bool, "message_id": str|None, "error": str|None}
    """
    if not settings.TERMII_API_KEY:
        logger.warning("TERMII_API_KEY not set — SMS not sent to %s", phone)
        return {"success": False, "error": "API key not configured"}

    payload = {
        "to":       phone,
        "from":     settings.TERMII_SENDER_ID,
        "sms":      message,
        "type":     "plain",
        "api_key":  settings.TERMII_API_KEY,
        "channel":  "generic",
    }
    try:
        resp = requests.post(
            f"{settings.TERMII_BASE_URL}/sms/send",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == "ok":
            return {"success": True, "message_id": data.get("message_id")}
        return {"success": False, "error": data.get("message", "Unknown error")}
    except Exception as exc:
        logger.exception("SMS send failed for %s: %s", phone, exc)
        return {"success": False, "error": str(exc)}


# ── WhatsApp via Termii ───────────────────────────────────────────────────────

def send_whatsapp(phone: str, message: str) -> dict:
    """Send WhatsApp message via Termii's WhatsApp channel."""
    if not settings.TERMII_API_KEY:
        logger.warning("TERMII_API_KEY not set — WhatsApp not sent to %s", phone)
        return {"success": False, "error": "API key not configured"}

    payload = {
        "to":      phone,
        "from":    settings.TERMII_SENDER_ID,
        "sms":     message,
        "type":    "plain",
        "api_key": settings.TERMII_API_KEY,
        "channel": "whatsapp",
    }
    try:
        resp = requests.post(
            f"{settings.TERMII_BASE_URL}/sms/send",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == "ok":
            return {"success": True, "message_id": data.get("message_id")}
        return {"success": False, "error": data.get("message", "Unknown error")}
    except Exception as exc:
        logger.exception("WhatsApp send failed for %s: %s", phone, exc)
        return {"success": False, "error": str(exc)}


# ── Email via SendGrid ────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body: str) -> dict:
    """Send email via SendGrid."""
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set — email not sent to %s", to_email)
        return {"success": False, "error": "API key not configured"}

    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from":    {"email": settings.DEFAULT_FROM_EMAIL, "name": "Assured Express Ops"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers=headers,
            json=payload,
            timeout=15,
        )
        if resp.status_code == 202:
            return {"success": True}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        logger.exception("Email send failed for %s: %s", to_email, exc)
        return {"success": False, "error": str(exc)}


# ── Firebase Push (Rider in-app) ──────────────────────────────────────────────

def send_push(fcm_token: str, title: str, body: str, priority: str = "normal") -> dict:
    """
    Send a Firebase push notification to a rider's device.
    priority: "normal" | "high" | "urgent" (urgent maps to FCM high + data flag)
    """
    if not settings.FIREBASE_CREDENTIALS_JSON:
        logger.warning("FIREBASE_CREDENTIALS_JSON not set — push not sent")
        return {"success": False, "error": "Firebase not configured"}

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred_data = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_data)
            firebase_admin.initialize_app(cred)

        fcm_priority = "high" if priority in ("high", "urgent") else "normal"
        message = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(title=title, body=body),
            android=messaging.AndroidConfig(priority=fcm_priority),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10" if fcm_priority == "high" else "5"}
            ),
            data={"priority": priority, "type": "broadcast"},
        )
        msg_id = messaging.send(message)
        return {"success": True, "message_id": msg_id}

    except Exception as exc:
        logger.exception("Push send failed for token %s…: %s", fcm_token[:10], exc)
        return {"success": False, "error": str(exc)}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def deliver_to_merchant(delivery, merchant, body: str, subject: str = "") -> None:
    """Dispatch a BroadcastDelivery to a merchant across configured channels."""
    from .models import BroadcastDelivery

    context = {
        "name":    merchant.business_name,
        "zone":    merchant.zone.name,
        "captain": "",  # populated if zone captain name known
        "orders":  "",
        "days":    "",
    }
    msg = personalise(body, context)

    results = {}
    for channel in delivery.broadcast.channels:
        if channel == "sms" and merchant.phone:
            results["sms"] = send_sms(merchant.phone, msg)
        elif channel == "whatsapp":
            wa = merchant.whatsapp or merchant.phone
            if wa:
                results["whatsapp"] = send_whatsapp(wa, msg)
        elif channel == "email" and merchant.email:
            subj = personalise(subject or "Message from Assured Express", context)
            results["email"] = send_email(merchant.email, subj, msg)

    success = any(r.get("success") for r in results.values())
    delivery.status = BroadcastDelivery.DeliveryStatus.DELIVERED if success else BroadcastDelivery.DeliveryStatus.FAILED
    delivery.sent_at = timezone.now()
    delivery.error_msg = str(results) if not success else ""
    delivery.save()


def deliver_to_rider(delivery, rider, body: str, title: str, priority: str) -> None:
    """Dispatch a BroadcastDelivery to a rider via in-app push."""
    from .models import BroadcastDelivery, RiderInAppNotification

    context = {
        "name":   rider.full_name,
        "zone":   rider.zone.name,
        "pct":    "",
        "orders": "",
        "target": "",
        "gap":    "",
    }
    msg = personalise(body, context)

    # Always create the in-app notification record (visible in app without push)
    RiderInAppNotification.objects.create(
        rider=rider,
        broadcast=delivery.broadcast,
        title=title,
        body=msg,
        priority=priority,
    )

    # Fire FCM push if token is available
    if hasattr(rider, "user_account") and rider.user_account.firebase_token:
        result = send_push(rider.user_account.firebase_token, title, msg, priority)
        delivery.status = (BroadcastDelivery.DeliveryStatus.DELIVERED
                           if result["success"]
                           else BroadcastDelivery.DeliveryStatus.SENT)  # SENT = in-app only
    else:
        delivery.status = BroadcastDelivery.DeliveryStatus.SENT

    delivery.sent_at = timezone.now()
    delivery.save()
