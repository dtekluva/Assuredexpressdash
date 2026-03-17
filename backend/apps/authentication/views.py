from rest_framework import serializers, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

User = get_user_model()


# ── Serializers ──────────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    vertical_name = serializers.CharField(source="vertical.name", read_only=True)
    zone_name     = serializers.CharField(source="zone.name",     read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "phone", "avatar", "vertical", "vertical_name",
            "zone", "zone_name", "last_seen",
        ]
        read_only_fields = ["id", "last_seen"]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT payload enriched with role and linked entity."""
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"]     = user.role
        token["name"]     = user.get_full_name()
        token["vertical"] = user.vertical_id
        token["zone"]     = user.zone_id
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


SIGNUP_ROLES = {User.Role.VERTICAL_LEAD, User.Role.ZONE_CAPTAIN}


class SignUpSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150)
    email      = serializers.EmailField()
    phone      = serializers.CharField(max_length=20)
    password   = serializers.CharField(min_length=8, write_only=True)
    role       = serializers.ChoiceField(choices=[
        (User.Role.VERTICAL_LEAD, "Vertical Lead"),
        (User.Role.ZONE_CAPTAIN, "Zone Captain"),
    ])
    vertical   = serializers.IntegerField(help_text="Required for both roles")
    zone       = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Required for zone_captain role",
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        from apps.core.models import Vertical, Zone

        # Vertical must exist
        try:
            vertical = Vertical.objects.get(pk=data["vertical"], is_active=True)
        except Vertical.DoesNotExist:
            raise serializers.ValidationError({"vertical": "Invalid or inactive vertical."})
        data["_vertical"] = vertical

        # Zone captain must supply a valid zone in that vertical
        if data["role"] == User.Role.ZONE_CAPTAIN:
            zone_id = data.get("zone")
            if not zone_id:
                raise serializers.ValidationError({"zone": "Zone is required for zone captains."})
            try:
                zone = Zone.objects.get(pk=zone_id, vertical=vertical, is_active=True)
            except Zone.DoesNotExist:
                raise serializers.ValidationError({"zone": "Invalid zone or zone not in selected vertical."})
            data["_zone"] = zone
        else:
            data["_zone"] = None

        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone=validated_data["phone"],
            role=validated_data["role"],
            vertical=validated_data["_vertical"],
            zone=validated_data["_zone"],
            is_active=True,
        )
        return user


# ── Views ────────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class SignUpView(APIView):
    """Self-registration for Vertical Leads and Zone Captains."""
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
    """Public endpoint returning verticals + zones for sign-up dropdowns."""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.core.models import Vertical, Zone
        verticals = list(
            Vertical.objects.filter(is_active=True)
            .values("id", "name", "full_name")
            .order_by("name")
        )
        zones = list(
            Zone.objects.filter(is_active=True)
            .values("id", "name", "vertical_id")
            .order_by("name")
        )
        return Response({"verticals": verticals, "zones": zones})


class UpdateFCMTokenView(APIView):
    """Riders call this on app launch to register their push token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateFCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.firebase_token = serializer.validated_data["firebase_token"]
        request.user.save(update_fields=["firebase_token"])
        return Response({"detail": "FCM token updated."})
