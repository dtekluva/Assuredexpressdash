from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Only super admins can perform admin CRUD operations."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "super_admin"


class IsAdminOrZoneLead(BasePermission):
    """Super admins and zone leads can see all zone data."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            "super_admin", "zone_lead", "ops_analyst"
        )


class CanViewHub(BasePermission):
    """Hub captains can only see their own hub."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in ("super_admin", "ops_analyst"):
            return True
        if user.role == "zone_lead":
            return obj.zone_id == user.zone_id
        if user.role == "hub_captain":
            return obj.id == user.hub_id
        return False


class IsSelfOrAdmin(BasePermission):
    """Riders can only see their own profile and orders."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == "super_admin":
            return True
        if user.role == "rider" and hasattr(obj, "rider_profile"):
            return obj.id == user.rider_profile_id
        return True
