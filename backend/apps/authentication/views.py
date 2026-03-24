from rest_framework import serializers, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ── Serializers ──────────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    hub_name  = serializers.CharField(source="hub.name",  read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "phone", "avatar", "zone", "zone_name",
            "hub", "hub_name", "last_seen",
        ]
        read_only_fields = ["id", "last_seen"]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT payload enriched with role and linked entity."""
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"]  = user.role
        token["name"]  = user.get_full_name()
        token["zone"]  = user.zone_id
        token["hub"]   = user.hub_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        user.last_seen = timezone.now()
        user.save(update_fields=["last_seen"])
        data["user"] = UserProfileSerializer(user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class UpdateFCMTokenSerializer(serializers.Serializer):
    firebase_token = serializers.CharField(required=True)


def _fetch_signup_options():
    """Fetch zones + hubs from AXpress. Returns (zones, hubs) lists."""
    from apps.core.axpress_client import get_zones, get_zone_detail

    raw = get_zones()
    zone_list = raw if isinstance(raw, list) else raw.get("verticals", raw.get("results", []))

    zones = []
    hubs = []
    for z in zone_list:
        zid = z["id"]
        zname = z.get("name", "")
        zones.append({"id": zid, "name": zname, "lead_name": z.get("lead_name", "")})

        # Fetch detail to get hubs
        detail = get_zone_detail(zid)
        for h in detail.get("zones", []):
            hubs.append({"id": h["id"], "name": h.get("name", ""), "zone_id": zid})

    return zones, hubs


class SignUpSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150)
    email      = serializers.EmailField()
    phone      = serializers.CharField(max_length=20)
    password   = serializers.CharField(min_length=8, write_only=True)
    role       = serializers.ChoiceField(choices=[
        (User.Role.ZONE_LEAD, "Zone Lead"),
        (User.Role.HUB_CAPTAIN, "Hub Captain"),
    ])
    zone       = serializers.CharField(help_text="AXpress zone UUID (was vertical)")
    hub        = serializers.CharField(
        required=False, allow_null=True, default=None,
        help_text="AXpress hub UUID (was zone) — required for hub_captain role",
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        from apps.core.axpress_client import AXpressAPIError

        try:
            zones, hubs = _fetch_signup_options()
        except AXpressAPIError:
            raise serializers.ValidationError("Unable to validate options. Please try again.")

        # Validate zone
        zone_match = next((z for z in zones if z["id"] == data["zone"]), None)
        if not zone_match:
            raise serializers.ValidationError({"zone": "Invalid zone."})
        data["_zone_name"] = zone_match["name"]

        # Hub captain must supply a valid hub in that zone
        if data["role"] == User.Role.HUB_CAPTAIN:
            if not data.get("hub"):
                raise serializers.ValidationError({"hub": "Hub is required for hub captains."})
            hub_match = next(
                (h for h in hubs if h["id"] == data["hub"] and h["zone_id"] == data["zone"]),
                None,
            )
            if not hub_match:
                raise serializers.ValidationError({"hub": "Invalid hub or hub not in selected zone."})
            data["_hub_name"] = hub_match["name"]
        else:
            data["_hub_name"] = None

        return data

    def create(self, validated_data):
        from apps.core.models import Zone, Hub

        # Get or create local Zone record so the FK works
        local_zone, _ = Zone.objects.get_or_create(
            name=validated_data["_zone_name"],
            defaults={"full_name": validated_data["_zone_name"]},
        )

        local_hub = None
        if validated_data.get("_hub_name"):
            local_hub, _ = Hub.objects.get_or_create(
                name=validated_data["_hub_name"],
                zone=local_zone,
                defaults={"slug": validated_data["_hub_name"].lower().replace(" ", "-")},
            )

        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone=validated_data["phone"],
            role=validated_data["role"],
            zone=local_zone,
            hub=local_hub,
            is_active=True,
        )
        return user


# ── Views ────────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class SignUpView(APIView):
    """Self-registration for Zone Leads and Hub Captains."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Issue JWT tokens so the user is logged in immediately
        token = CustomTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "access": str(token.access_token),
                "refresh": str(token),
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
            return Response({"detail": "Logged out successfully."})
        except Exception:
            return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password changed successfully."})


class SignUpOptionsView(APIView):
    """Public endpoint returning zones + hubs for sign-up dropdowns."""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.core.axpress_client import AXpressAPIError

        try:
            zones, hubs = _fetch_signup_options()
        except AXpressAPIError:
            return Response(
                {"detail": "Unable to fetch options. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"zones": zones, "hubs": hubs})


class UpdateFCMTokenView(APIView):
    """Riders call this on app launch to register their push token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateFCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.firebase_token = serializer.validated_data["firebase_token"]
        request.user.save(update_fields=["firebase_token"])
        return Response({"detail": "FCM token updated."})
