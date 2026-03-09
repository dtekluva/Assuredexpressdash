from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("AE Profile", {"fields": ("role", "phone", "vertical", "zone", "rider_profile", "firebase_token")}),
    )
    list_display  = ["username", "get_full_name", "role", "vertical", "zone", "is_active"]
    list_filter   = ["role", "is_active", "vertical"]
    search_fields = ["username", "first_name", "last_name", "email", "phone"]
