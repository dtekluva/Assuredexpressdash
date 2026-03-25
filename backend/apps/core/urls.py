"""
OCC core URL routes.

All endpoints proxy data from the main AXpress backend.
The comms app has its own urls.py for local communication features.

Hierarchy: Zone (top-level) → Relay Nodes (physical handoff points).
Riders and merchants belong to zones. Verticals are deprecated.
"""
from django.urls import path

from .views import (
    DashboardSummaryView,
    ZoneListView,
    ZoneDetailView,
    ZoneRidersView,
    ZoneMerchantsView,
    ZoneCRUDListView,
    ZoneCRUDDetailView,
    HubListView,
    HubCRUDListView,
    HubCRUDDetailView,
    HubTargetListView,
    HubTargetDetailView,
    RelayNodeListView,
    RelayNodeDetailView,
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

    # Zones (top-level — was Verticals, now powered by /api/occ/leaderboard/zones/)
    path("zones/", ZoneListView.as_view(), name="zone-list"),
    path("zones/<str:pk>/", ZoneDetailView.as_view(), name="zone-detail"),
    path("zones/<str:pk>/performance/", ZoneDetailView.as_view(), name="zone-performance"),  # alias
    path("zones/<str:pk>/riders/", ZoneRidersView.as_view(), name="zone-riders"),
    path("zones/<str:pk>/merchants/", ZoneMerchantsView.as_view(), name="zone-merchants"),

    # Hubs (dispatch zones — kept for admin CRUD and listing)
    path("hubs/", HubListView.as_view(), name="hub-list"),

    # Relay Nodes (physical handoff points within zones)
    path("relay-nodes/", RelayNodeListView.as_view(), name="relay-node-list"),
    path("relay-nodes/<str:pk>/", RelayNodeDetailView.as_view(), name="relay-node-detail"),

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

    # Admin — Super admin CRUD for zones, hubs, and targets
    path("admin/zones/", ZoneCRUDListView.as_view(), name="admin-zone-list"),
    path("admin/zones/<str:pk>/", ZoneCRUDDetailView.as_view(), name="admin-zone-detail"),
    path("admin/hubs/", HubCRUDListView.as_view(), name="admin-hub-list"),
    path("admin/hubs/<str:pk>/", HubCRUDDetailView.as_view(), name="admin-hub-detail"),
    path("admin/hub-targets/", HubTargetListView.as_view(), name="admin-hub-target-list"),
    path("admin/hub-targets/<str:pk>/", HubTargetDetailView.as_view(), name="admin-hub-target-detail"),

    # Admin — Rider reassignment
    path("admin/riders/reassign/", RiderReassignView.as_view(), name="admin-rider-reassign"),
    path("admin/riders/bulk-reassign/", RiderBulkReassignView.as_view(), name="admin-rider-bulk-reassign"),
]
