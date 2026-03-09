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


# ── Views ────────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


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


class UpdateFCMTokenView(APIView):
    """Riders call this on app launch to register their push token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateFCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.firebase_token = serializer.validated_data["firebase_token"]
        request.user.save(update_fields=["firebase_token"])
        return Response({"detail": "FCM token updated."})
