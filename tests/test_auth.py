import pytest


@pytest.mark.django_db
def test_register_login_and_me(api):
    r = api.post(
        "/api/auth/register/",
        {"email": "new@example.com", "username": "new", "password": "S3cure-pass-987"},
        format="json",
    )
    assert r.status_code == 201
    assert "password" not in r.data

    r = api.post(
        "/api/auth/login/",
        {"email": "new@example.com", "password": "S3cure-pass-987"},
        format="json",
    )
    assert r.status_code == 200
    token = r.data["access"]

    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r = api.get("/api/auth/me/")
    assert r.status_code == 200
    assert r.data["email"] == "new@example.com"


@pytest.mark.django_db
def test_me_requires_auth(api):
    assert api.get("/api/auth/me/").status_code == 401
