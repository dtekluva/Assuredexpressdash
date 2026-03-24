"""
python manage.py seed_data

Populates the database with all 4 zones, 21 hubs, riders,
200 merchants, and 6 months of synthetic snapshot data for development.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from apps.core.models import (
    Zone, Hub, Rider, Merchant, RiderSnapshot, MerchantSnapshot
)

User = get_user_model()

ZONES = [
    {"name": "Dennis",     "full_name": "Dennis — Island & Lekki Corridor", "color_hex": "#3B82F6"},
    {"name": "Seun",       "full_name": "Seun — Central Mainland",          "color_hex": "#10B981"},
    {"name": "Erinfolami", "full_name": "Erinfolami — Southwest Mainland",  "color_hex": "#A855F7"},
    {"name": "Mary",       "full_name": "Mary — North & Ikorodu",           "color_hex": "#F59E0B"},
]

HUBS_PER_ZONE = [
    ["Osapa/Jakande", "Awoyaya", "Ajah", "Obalende"],
    ["Oshodi", "Oyingbo", "Tejuosho", "Sabo", "Bariga", "Ajegunle"],
    ["Festac", "Iyana ipaja/egbeda", "Ikotun", "Tradefair", "Iyana Iba", "Ayobo"],
    ["Agege", "Ikeja", "Mile12", "Ikorodu", "Berger"],
]

RIDER_FIRST = ["Emeka", "Tunde", "Chukwudi", "Bola", "Kola", "Festus", "Deji", "Victor",
               "Ola", "Seun", "Moses", "Jide", "Frank", "Amos", "Dare", "Gbenga",
               "Kayode", "Tony", "Remi", "Uche", "Lanre", "Nnamdi", "Femi", "Peter",
               "Bayo", "Chidi", "Yemi", "Kazeem", "Dayo", "Abel"]
RIDER_LAST  = ["Okafor", "Adewale", "Eze", "Rasheed", "Mensah", "Anya", "Okon", "Nweze",
               "Bakare", "Alabi", "Chidi", "Ogundele", "Okeke", "Taiwo", "Olamide",
               "Sule", "Akin", "Obiora", "Adeyemi", "Nwosu", "Oduya", "Eze2", "Alade",
               "Achike", "Oloro", "Ogunleke", "Nwachukwu", "Adediran", "Bello", "Fagbemi"]

MERCHANT_NAMES = [
    "Mama Nkechi Foods", "Lagos Cakes & Bites", "Zara Fashion Hub", "TechGadgets NG",
    "FreshMart Groceries", "Sisi Eko Boutique", "PharmaCare Plus", "BabyWorld Store",
    "SportZone Lagos", "HomeDecor Express",
]
BUSINESS_TYPES = [
    "Food & Grocery", "Fashion & Apparel", "Pharmacy", "Electronics",
    "Bakery & Confections", "Beauty & Cosmetics", "Hardware", "Baby & Kids",
    "Sports & Fitness", "Home & Décor",
]


class Command(BaseCommand):
    help = "Seed the database with demo data for development"

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=6,
                            help="Months of snapshot history to generate")
        parser.add_argument("--clear", action="store_true",
                            help="Clear existing data before seeding")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data…")
            MerchantSnapshot.objects.all().delete()
            RiderSnapshot.objects.all().delete()
            Merchant.objects.all().delete()
            Rider.objects.all().delete()
            Hub.objects.all().delete()
            Zone.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        self.stdout.write("Creating superuser admin…")
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@assuredexpress.ng", "admin123",
                                          first_name="Admin", last_name="User")

        self.stdout.write("Creating zones…")
        zones = []
        for i, zdata in enumerate(ZONES):
            z, _ = Zone.objects.get_or_create(name=zdata["name"], defaults={
                **zdata,
                "base_pay": 250_000,
                "transport_pay": 80_000,
                "commission_rate": Decimal("0.0110"),
            })
            zones.append(z)

        self.stdout.write("Creating hubs, riders, merchants…")
        rng = random.Random(42)

        for zi, zone in enumerate(zones):
            # Create zone lead user
            lead_username = f"lead_{zone.name.lower()}"
            lead, _ = User.objects.get_or_create(username=lead_username, defaults={
                "first_name": zone.name,
                "last_name": "Lead",
                "email": f"{lead_username}@assuredexpress.ng",
                "role": "zone_lead",
                "zone": zone,
            })
            if not lead.has_usable_password():
                lead.set_password("demo1234")
                lead.save()

            for hi, hub_name in enumerate(HUBS_PER_ZONE[zi]):
                hub, _ = Hub.objects.get_or_create(
                    zone=zone,
                    name=hub_name,
                    defaults={
                        "slug": slugify(f"{zone.name}-{hub_name}"),
                        "order_target": 2000,
                        "revenue_target": 3_000_000,
                        "base_pay": 50_000,
                        "transport_pay": 40_000,
                        "commission_rate": Decimal("0.0400"),
                    }
                )

                # Hub captain user
                gi = zi * 5 + hi
                cap_first = RIDER_FIRST[gi % len(RIDER_FIRST)]
                cap_last  = RIDER_LAST[gi % len(RIDER_LAST)]
                cap_username = f"captain_{hub.slug}"
                cap, _ = User.objects.get_or_create(username=cap_username, defaults={
                    "first_name": cap_first,
                    "last_name": cap_last,
                    "email": f"{cap_username}@assuredexpress.ng",
                    "role": "hub_captain",
                    "zone": zone,
                    "hub": hub,
                })
                if not cap.has_usable_password():
                    cap.set_password("demo1234")
                    cap.save()

                # 5 riders per hub
                riders = []
                for ri in range(5):
                    seed = gi * 31 + ri * 17 + 7
                    r_first = RIDER_FIRST[(seed * 3 + ri) % len(RIDER_FIRST)]
                    r_last  = RIDER_LAST[(seed * 7 + ri) % len(RIDER_LAST)]
                    phone   = f"080{rng.randint(10000000, 99999999)}"
                    rider, _ = Rider.objects.get_or_create(phone=phone, defaults={
                        "hub": hub,
                        "first_name": r_first,
                        "last_name": r_last,
                        "email": f"rider.{phone}@assuredexpress.ng",
                        "status": "active",
                        "joined_at": date(2024, rng.randint(1, 6), rng.randint(1, 28)),
                    })
                    riders.append(rider)

                # 10 merchants per hub
                for mi in range(10):
                    seed = gi * 53 + mi * 19 + 41
                    m_phone = f"070{rng.randint(10000000, 99999999)}"
                    merchant, _ = Merchant.objects.get_or_create(phone=m_phone, defaults={
                        "hub": hub,
                        "business_name": MERCHANT_NAMES[mi % len(MERCHANT_NAMES)],
                        "business_type": BUSINESS_TYPES[mi % len(BUSINESS_TYPES)],
                        "owner_name": f"{RIDER_FIRST[(seed+mi)%len(RIDER_FIRST)]} {RIDER_LAST[(seed*2+mi)%len(RIDER_LAST)]}",
                        "email": f"merchant.{m_phone}@business.ng",
                        "status": rng.choices(["active", "active", "active", "watch", "inactive"],
                                              weights=[50, 20, 10, 15, 5])[0],
                        "onboarded_at": date(2024, rng.randint(1, 6), rng.randint(1, 28)),
                    })

                    # Generate merchant snapshots
                    today = date.today()
                    for day_offset in range(options["months"] * 30):
                        snap_date = today - timedelta(days=day_offset)
                        if snap_date.weekday() >= 5:  # skip weekends
                            continue
                        if rng.random() < 0.15:  # ~15% chance merchant inactive on a day
                            continue
                        orders = rng.randint(0, 6)
                        fulfilled = max(0, orders - rng.randint(0, 1))
                        aov = rng.randint(1500, 15000)
                        MerchantSnapshot.objects.get_or_create(
                            merchant=merchant,
                            date=snap_date,
                            defaults={
                                "orders_placed": orders,
                                "orders_fulfilled": fulfilled,
                                "orders_returned": max(0, orders - fulfilled),
                                "gross_revenue": fulfilled * aov,
                                "avg_order_value": aov,
                            }
                        )

                # Generate rider snapshots
                today = date.today()
                for rider in riders:
                    seed = hash(rider.phone) % 1000
                    perf = 0.45 + rng.uniform(0, 0.55)
                    for day_offset in range(options["months"] * 30):
                        snap_date = today - timedelta(days=day_offset)
                        if snap_date.weekday() >= 5:
                            continue
                        if rng.random() < (0.15 * (1 - perf)):  # lower performers offline more
                            continue
                        base_orders = int(400 / 26 * perf * rng.uniform(0.7, 1.3))
                        orders = max(0, base_orders)
                        rejected = rng.randint(0, max(1, int(orders * 0.1)))
                        failed   = rng.randint(0, max(1, int(orders * 0.05)))
                        km = orders * rng.uniform(3.5, 5.5)
                        revenue = orders * rng.randint(18000, 28000)
                        ghost_mins = rng.randint(0, 45) if rng.random() < 0.1 else 0
                        RiderSnapshot.objects.get_or_create(
                            rider=rider,
                            date=snap_date,
                            defaults={
                                "orders_completed":   orders,
                                "orders_rejected":    rejected,
                                "orders_failed":      failed,
                                "km_covered":         round(km, 2),
                                "revenue_generated":  revenue,
                                "online_minutes":     rng.randint(300, 540),
                                "peak_orders":        int(orders * rng.uniform(0.4, 0.8)),
                                "avg_delivery_mins":  rng.uniform(20, 50),
                                "csat_sum":           rng.uniform(3.0, 5.0) * orders,
                                "csat_count":         orders,
                                "ghost_minutes":      ghost_mins,
                                "has_ghost_flag":     ghost_mins > 30,
                            }
                        )

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Seed complete!\n"
            f"   Zones:     {Zone.objects.count()}\n"
            f"   Hubs:      {Hub.objects.count()}\n"
            f"   Riders:    {Rider.objects.count()}\n"
            f"   Merchants: {Merchant.objects.count()}\n"
            f"   Rider snapshots:    {RiderSnapshot.objects.count()}\n"
            f"   Merchant snapshots: {MerchantSnapshot.objects.count()}\n\n"
            f"   🔑 Admin login: admin / admin123\n"
            f"   🔑 Demo lead:   lead_dennis / demo1234\n"
            f"   🔑 Demo captain: captain_dennis-awoyaya / demo1234\n"
        ))
