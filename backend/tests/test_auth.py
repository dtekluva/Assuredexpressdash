"""
Tests for authentication endpoints.
Run:  pytest tests/test_auth.py -v
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import UserFactory, ZoneFactory, HubFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory(password="strongpass99")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    resp = client.post(reverse("auth-login"), {"username": user.username, "password": "strongpass99"})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return client, resp.data


@pytest.mark.django_db
class TestLogin:
    def test_valid_login_returns_tokens(self, api_client, user):
        resp = api_client.post(reverse("auth-login"), {
            "username": user.username,
            "password": "strongpass99",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "access"  in resp.data
        assert "refresh" in resp.data
        assert "user"    in resp.data
        assert resp.data["user"]["role"] == user.role

    def test_invalid_credentials_returns_401(self, api_client, user):
        resp = api_client.post(reverse("auth-login"), {
            "username": user.username,
            "password": "wrongpassword",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_fields_returns_400(self, api_client):
        resp = api_client.post(reverse("auth-login"), {"username": "someone"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_jwt_payload_contains_role(self, api_client, user):
        resp = api_client.post(reverse("auth-login"), {"username": user.username, "password": "strongpass99"})
        import jwt
        payload = jwt.decode(resp.data["access"], options={"verify_signature": False})
        assert payload["role"] == user.role


@pytest.mark.django_db
class TestProfile:
    def test_get_own_profile(self, auth_client):
        client, data = auth_client
        resp = client.get(reverse("auth-profile"))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["username"] == data["user"]["username"]

    def test_unauthenticated_profile_returns_401(self, api_client):
        resp = api_client.get(reverse("auth-profile"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_profile_updates_phone(self, auth_client):
        client, _ = auth_client
        resp = client.patch(reverse("auth-profile"), {"phone": "08099998888"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["phone"] == "08099998888"


@pytest.mark.django_db
class TestChangePassword:
    def test_correct_old_password_changes_password(self, auth_client, user):
        client, _ = auth_client
        resp = client.post(reverse("auth-change-password"), {
            "old_password": "strongpass99",
            "new_password": "newstrongpass99",
        })
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("newstrongpass99")

    def test_wrong_old_password_returns_400(self, auth_client):
        client, _ = auth_client
        resp = client.post(reverse("auth-change-password"), {
            "old_password": "wrongoldpass",
            "new_password": "newpass123",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogout:
    def test_logout_blacklists_refresh(self, api_client, user):
        login_resp = api_client.post(reverse("auth-login"), {"username": user.username, "password": "strongpass99"})
        access  = login_resp.data["access"]
        refresh = login_resp.data["refresh"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_resp = api_client.post(reverse("auth-logout"), {"refresh": refresh})
        assert logout_resp.status_code == status.HTTP_200_OK

        # Second logout with same refresh should fail
        refresh_resp = api_client.post(reverse("token-refresh"), {"refresh": refresh})
        assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED
