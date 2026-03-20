from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Only super admins can perform admin CRUD operations."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "super_admin"


class IsAdminOrVerticalLead(BasePermission):
    """Super admins and vertical leads can see all vertical data."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            "super_admin", "vertical_lead", "ops_analyst"
        )


class CanViewZone(BasePermission):
    """Zone captains can only see their own zone."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in ("super_admin", "ops_analyst"):
            return True
        if user.role == "vertical_lead":
            return obj.vertical_id == user.vertical_id
        if user.role == "zone_captain":
            return obj.id == user.zone_id
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
