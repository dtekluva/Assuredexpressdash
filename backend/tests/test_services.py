"""
Unit tests for the services layer — metric computation logic.
These tests do not hit the network or external services.
Run:  pytest tests/test_services.py -v
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from tests.factories import RiderFactory, MerchantFactory, RiderSnapshotFactory
from apps.core.services import (
    compute_rider_metrics, compute_merchant_metrics, scale_target,
    MONTHLY_ORDERS_TARGET, MONTHLY_REVENUE_TARGET, WORKING_DAYS_MONTH,
)


@pytest.mark.django_db
class TestScaleTarget:
    def test_full_month_returns_base(self):
        start = date(2025, 1, 1)
        end   = date(2025, 1, 26)
        result = scale_target(MONTHLY_ORDERS_TARGET, start, end)
        assert result == MONTHLY_ORDERS_TARGET

    def test_half_month_returns_half(self):
        start = date(2025, 1, 1)
        end   = date(2025, 1, 13)
        result = scale_target(MONTHLY_ORDERS_TARGET, start, end)
        # 13 / 26 = 50%
        assert result == round(MONTHLY_ORDERS_TARGET * 13 / WORKING_DAYS_MONTH)

    def test_single_day_returns_daily_target(self):
        today = date.today()
        result = scale_target(MONTHLY_ORDERS_TARGET, today, today)
        assert result == round(MONTHLY_ORDERS_TARGET / WORKING_DAYS_MONTH)


@pytest.mark.django_db
class TestComputeRiderMetrics:
    def test_zero_snapshots_returns_zero_metrics(self):
        rider = RiderFactory()
        start = date.today() - timedelta(days=7)
        end   = date.today()
        metrics = compute_rider_metrics(rider, start, end)

        assert metrics["orders_completed"] == 0
        assert metrics["revenue"]          == 0
        assert metrics["pct"]              == 0
        assert metrics["flags"]            == []

    def test_orders_and_revenue_aggregated_correctly(self):
        rider = RiderFactory()
        start = date.today() - timedelta(days=4)
        end   = date.today()

        # 3 snapshots: 20 orders each = 60 total
        for i in range(3):
            RiderSnapshotFactory(
                rider=rider,
                date=start + timedelta(days=i),
                orders_completed=20,
                revenue_generated=400_000,
            )

        metrics = compute_rider_metrics(rider, start, end)
        assert metrics["orders_completed"] == 60
        assert metrics["revenue"]          == 1_200_000

    def test_attainment_pct_calculation(self):
        rider = RiderFactory()
        start = date(2025, 6, 1)
        end   = date(2025, 6, 26)  # Full month (26 working days)

        # Create 13 days × 20 orders = 260 orders (65% of 400)
        for i in range(13):
            RiderSnapshotFactory(
                rider=rider,
                date=start + timedelta(days=i),
                orders_completed=20,
            )

        metrics = compute_rider_metrics(rider, start, end)
        assert metrics["pct"] == 65

    def test_ghost_flag_generated_for_high_ghost_ratio(self):
        rider = RiderFactory()
        today = date.today()
        RiderSnapshotFactory(
            rider=rider, date=today,
            ghost_minutes=200,   # very high
            online_minutes=60,
        )
        metrics = compute_rider_metrics(rider, today, today)
        # Should have at least the ghost flag
        flag_types = [f["msg"] for f in metrics["flags"]]
        assert any("ghost" in msg.lower() for msg in flag_types)

    def test_low_acceptance_rate_triggers_flag(self):
        rider = RiderFactory()
        today = date.today()
        RiderSnapshotFactory(
            rider=rider, date=today,
            orders_completed=10,
            orders_rejected=40,  # 20% acceptance rate
        )
        metrics = compute_rider_metrics(rider, today, today)
        flag_msgs = [f["msg"] for f in metrics["flags"]]
        assert any("acceptance" in m.lower() for m in flag_msgs)

    def test_csat_average_computed_correctly(self):
        rider = RiderFactory()
        today = date.today()
        RiderSnapshotFactory(
            rider=rider, date=today,
            csat_sum=45.0,   # 45 / 10 = 4.5
            csat_count=10,
        )
        metrics = compute_rider_metrics(rider, today, today)
        assert metrics["csat_avg"] == 4.5

    def test_metrics_with_detailed_includes_history(self):
        rider = RiderFactory()
        today = date.today()
        RiderSnapshotFactory(rider=rider, date=today)
        metrics = compute_rider_metrics(rider, today, today, detailed=True)
        assert "order_history"   in metrics
        assert "revenue_history" in metrics


@pytest.mark.django_db
class TestComputeMerchantMetrics:
    def test_zero_snapshots_returns_zero_metrics(self):
        merchant = MerchantFactory()
        start = date.today() - timedelta(days=7)
        end   = date.today()
        metrics = compute_merchant_metrics(merchant, start, end)

        assert metrics["orders_placed"]    == 0
        assert metrics["orders_fulfilled"] == 0
        assert metrics["gross_revenue"]    == 0
        assert metrics["fulfillment_rate"] == 0

    def test_fulfillment_rate_calculation(self):
        from tests.factories import RiderSnapshotFactory
        from apps.core.models import MerchantSnapshot

        merchant = MerchantFactory()
        today = date.today()
        MerchantSnapshot.objects.create(
            merchant=merchant,
            date=today,
            orders_placed=10,
            orders_fulfilled=8,
            orders_returned=2,
            gross_revenue=80_000,
            avg_order_value=10_000,
        )
        metrics = compute_merchant_metrics(merchant, today, today)
        assert metrics["orders_placed"]    == 10
        assert metrics["orders_fulfilled"] == 8
        assert metrics["fulfillment_rate"] == 80.0


@pytest.mark.django_db
class TestPersonaliseService:
    def test_token_replacement(self):
        from apps.comms.services import personalise
        template = "Hi {name}, you have {orders} orders in {zone}."
        result = personalise(template, {"name": "Ade", "orders": "15", "zone": "Ajah"})
        assert result == "Hi Ade, you have 15 orders in Ajah."

    def test_missing_token_left_as_is(self):
        from apps.comms.services import personalise
        template = "Hi {name}, your target is {target}."
        result = personalise(template, {"name": "Ade"})
        assert "{target}" in result
        assert "Ade" in result
