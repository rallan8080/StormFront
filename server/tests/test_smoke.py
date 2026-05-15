import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_register_login_me_flow(client: AsyncClient) -> None:
    email = "ada@example.com"
    password = "correct-horse-battery-staple"

    reg = await client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text
    pair = reg.json()
    assert pair["tokenType"] == "Bearer"
    assert pair["expiresIn"] > 0

    me = await client.get("/me", headers={"Authorization": f"Bearer {pair['accessToken']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    bad = await client.post("/auth/login", json={"email": email, "password": "nope"})
    assert bad.status_code == 401


async def test_create_character_assigns_starting_room(client: AsyncClient) -> None:
    reg = await client.post(
        "/auth/register",
        json={"email": "grace@example.com", "password": "correct-horse-battery-staple"},
    )
    token = reg.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/characters", json={"name": "Grace"}, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Grace"
    assert body["currentRoomId"] == "town-square"

    listed = await client.get("/characters", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
