def test_register_and_login(client):
    r = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "root@example.com", "password": "Root12345", "full_name": "Root"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()["data"]
    assert payload["role"] == "SUPER_ADMIN"

    login = client.post(
        "/api/v1/auth/login", json={"email": "root@example.com", "password": "Root12345"}
    )
    assert login.status_code == 200
    assert login.json()["data"]["access_token"]


def test_register_super_admin_only_once(client):
    first = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "root@example.com", "password": "Root12345", "full_name": "Root"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "other@example.com", "password": "Root12345", "full_name": "Other"},
    )
    assert second.status_code in (409, 400)


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "root@example.com", "password": "Root12345", "full_name": "Root"},
    )
    bad = client.post("/api/v1/auth/login", json={"email": "root@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"
