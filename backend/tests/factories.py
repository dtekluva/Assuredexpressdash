"""
Factory Boy factories for all core models.
Usage in tests:
    rider = RiderFactory()
    zone  = ZoneFactory(vertical=VerticalFactory())
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
from decimal import Decimal
import random

fake = Faker()


class VerticalFactory(DjangoModelFactory):
    class Meta:
        model = "core.Vertical"

    name       = factory.Sequence(lambda n: f"V{n}")
    full_name  = factory.Sequence(lambda n: f"Vertical {n} — Lagos")
    color_hex  = factory.LazyFunction(lambda: f"#{random.randint(0, 0xFFFFFF):06x}")
    is_active  = True
    base_pay   = 250_000
    transport_pay = 80_000
    commission_rate = Decimal("0.0110")


class ZoneFactory(DjangoModelFactory):
    class Meta:
        model = "core.Zone"

    vertical       = factory.SubFactory(VerticalFactory)
    name           = factory.Sequence(lambda n: f"Zone {n}")
    slug           = factory.Sequence(lambda n: f"zone-{n}")
    is_active      = True
    order_target   = 2000
    revenue_target = 3_000_000
    base_pay       = 50_000
    transport_pay  = 40_000
    commission_rate = Decimal("0.0400")


class RiderFactory(DjangoModelFactory):
    class Meta:
        model = "core.Rider"

    zone       = factory.SubFactory(ZoneFactory)
    first_name = factory.LazyFunction(fake.first_name)
    last_name  = factory.LazyFunction(fake.last_name)
    phone      = factory.Sequence(lambda n: f"080{n:08d}")
    email      = factory.LazyAttribute(lambda o: f"{o.first_name.lower()}.{o.last_name.lower()}@ae.ng")
    status     = "active"
    joined_at  = factory.LazyFunction(lambda: date.today() - timedelta(days=random.randint(30, 365)))


class MerchantFactory(DjangoModelFactory):
    class Meta:
        model = "core.Merchant"

    zone          = factory.SubFactory(ZoneFactory)
    business_name = factory.LazyFunction(lambda: f"{fake.company()} Store")
    business_type = "Food & Grocery"
    owner_name    = factory.LazyFunction(fake.name)
    phone         = factory.Sequence(lambda n: f"070{n:08d}")
    email         = factory.LazyFunction(fake.email)
    status        = "active"
    onboarded_at  = factory.LazyFunction(lambda: date.today() - timedelta(days=random.randint(30, 180)))


class RiderSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = "core.RiderSnapshot"

    rider              = factory.SubFactory(RiderFactory)
    date               = factory.LazyFunction(lambda: date.today() - timedelta(days=1))
    orders_completed   = factory.LazyFunction(lambda: random.randint(8, 25))
    orders_rejected    = factory.LazyFunction(lambda: random.randint(0, 3))
    orders_failed      = factory.LazyFunction(lambda: random.randint(0, 2))
    km_covered         = factory.LazyFunction(lambda: round(random.uniform(40, 120), 2))
    revenue_generated  = factory.LazyFunction(lambda: random.randint(150_000, 600_000))
    online_minutes     = factory.LazyFunction(lambda: random.randint(300, 540))
    peak_orders        = factory.LazyFunction(lambda: random.randint(3, 10))
    csat_sum           = factory.LazyFunction(lambda: round(random.uniform(3.5, 5.0) * 15, 2))
    csat_count         = 15
    ghost_minutes      = 0
    has_ghost_flag     = False


class UserFactory(DjangoModelFactory):
    class Meta:
        model = "authentication.User"

    username   = factory.Sequence(lambda n: f"user{n}")
    email      = factory.LazyAttribute(lambda o: f"{o.username}@ae.ng")
    first_name = factory.LazyFunction(fake.first_name)
    last_name  = factory.LazyFunction(fake.last_name)
    role       = "ops_analyst"
    is_active  = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user


class ZoneCaptainFactory(UserFactory):
    role = "zone_captain"
    zone = factory.SubFactory(ZoneFactory)


class VerticalLeadFactory(UserFactory):
    role     = "vertical_lead"
    vertical = factory.SubFactory(VerticalFactory)
