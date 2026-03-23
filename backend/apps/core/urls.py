"""
OCC core URL routes.

All endpoints proxy data from the main AXpress backend.
The comms app has its own urls.py for local communication features.
"""
from django.urls import path

from .views import (
    DashboardSummaryView,
    VerticalListView,
    VerticalDetailView,
    VerticalCRUDListView,
    VerticalCRUDDetailView,
    ZoneDashboardView,
    ZoneListView,
    ZoneCRUDListView,
    ZoneCRUDDetailView,
    ZoneRidersView,
    ZoneMerchantsView,
    ZoneTargetListView,
    ZoneTargetDetailView,
    RiderPerformanceView,
    RiderLocationsView,
    RiderListView,
    RiderDetailView,
    RiderOrdersView,
    RiderReassignView,
    RiderBulkReassignView,
    MerchantAnalyticsView,
    MerchantListView,
    MerchantDetailView,
    LeaderboardView,
    OrderAnalyticsView,
    OrderListView,
    OrderDetailView,
    OrderAssignView,
)

urlpatterns = [
    # Dashboard
    path("dashboard/", DashboardSummaryView.as_view(), name="dashboard-summary"),

    # Verticals
    path("verticals/", VerticalListView.as_view(), name="vertical-list"),
    path("verticals/<str:pk>/", VerticalDetailView.as_view(), name="vertical-detail"),
    path("verticals/<str:pk>/performance/", VerticalDetailView.as_view(), name="vertical-performance"),  # alias

    # Zones — CRUD + analytics
    path("zones/", ZoneListView.as_view(), name="zone-list"),
    path("zones/<str:pk>/dashboard/", ZoneDashboardView.as_view(), name="zone-dashboard"),
    path("zones/<str:pk>/performance/", ZoneDashboardView.as_view(), name="zone-performance"),  # alias
    path("zones/<str:pk>/riders/", ZoneRidersView.as_view(), name="zone-riders"),
    path("zones/<str:pk>/merchants/", ZoneMerchantsView.as_view(), name="zone-merchants"),

    # Riders — CRUD + analytics
    path("riders/", RiderListView.as_view(), name="rider-list"),
    path("riders/locations/", RiderLocationsView.as_view(), name="rider-locations"),
    path("riders/<str:pk>/", RiderDetailView.as_view(), name="rider-detail"),
    path("riders/<str:pk>/performance/", RiderPerformanceView.as_view(), name="rider-performance"),
    path("riders/<str:pk>/orders/", RiderOrdersView.as_view(), name="rider-orders"),

    # Merchants — CRUD + analytics
    path("merchants/", MerchantListView.as_view(), name="merchant-list"),
    path("merchants/<str:pk>/", MerchantDetailView.as_view(), name="merchant-detail"),
    path("merchants/<str:pk>/analytics/", MerchantAnalyticsView.as_view(), name="merchant-analytics"),
    path("merchants/<str:pk>/performance/", MerchantAnalyticsView.as_view(), name="merchant-performance"),  # alias

    # Leaderboard
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),

    # Orders — CRUD + analytics
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/analytics/", OrderAnalyticsView.as_view(), name="order-analytics"),
    path("orders/<str:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:pk>/assign/", OrderAssignView.as_view(), name="order-assign"),

    # Admin — Super admin CRUD for verticals, zones, and targets
    path("admin/verticals/", VerticalCRUDListView.as_view(), name="admin-vertical-list"),
    path("admin/verticals/<str:pk>/", VerticalCRUDDetailView.as_view(), name="admin-vertical-detail"),
    path("admin/zones/", ZoneCRUDListView.as_view(), name="admin-zone-list"),
    path("admin/zones/<str:pk>/", ZoneCRUDDetailView.as_view(), name="admin-zone-detail"),
    path("admin/zone-targets/", ZoneTargetListView.as_view(), name="admin-zone-target-list"),
    path("admin/zone-targets/<str:pk>/", ZoneTargetDetailView.as_view(), name="admin-zone-target-detail"),

    # Admin — Rider reassignment
    path("admin/riders/reassign/", RiderReassignView.as_view(), name="admin-rider-reassign"),
    path("admin/riders/bulk-reassign/", RiderBulkReassignView.as_view(), name="admin-rider-bulk-reassign"),
]
