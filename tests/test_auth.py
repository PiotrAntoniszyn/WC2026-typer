"""Smoke tests for the auth blueprint."""
import pytest


def test_login_page_loads(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"Log In" in r.data


def test_register_page_loads(client):
    r = client.get("/register")
    assert r.status_code == 200
    assert b"Create Account" in r.data


def test_register_wrong_invite_code(client):
    r = client.post(
        "/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "invite_code": "WRONG",
            "csrf_token": "ignored",
        },
        follow_redirects=True,
    )
    # CSRF is disabled in testing; wrong invite code should re-render form
    assert r.status_code == 200


def test_login_with_bad_credentials(client):
    r = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "wrong", "csrf_token": "ignored"},
        follow_redirects=True,
    )
    assert r.status_code == 200
