from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.domain import AuthUser
from tests.conftest import auth
from tests.fakes import FakeHouseholdsRepository


async def create_household(
    client: AsyncClient, token: str = "owner", name: str = "Test Home"
) -> dict[str, Any]:
    response = await client.post(
        "/households",
        json={"name": name},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def join_household(
    client: AsyncClient, code: str, token: str = "member"
) -> dict[str, Any]:
    return (
        await client.post(
            "/households/join",
            json={"invite_code": code},
            headers=auth(token),
        )
    ).json()


async def test_health_is_public(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_auth_is_required(client: AsyncClient) -> None:
    response = await client.get("/households/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_create_household_makes_owner(
    client: AsyncClient, users: dict[str, AuthUser]
) -> None:
    body = await create_household(client, "owner", "Sharma Home")
    assert re.fullmatch(r"[A-Z2-9]{8}", body["invite_code"])
    assert body["name"] == "Sharma Home"
    assert body["role"] == "owner"
    assert len(body["members"]) == 1
    assert body["members"][0]["role"] == "owner"
    assert body["members"][0]["email"] == users["owner"].email

    me = await client.get("/households/me", headers=auth("owner"))
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


async def test_second_create_is_rejected(client: AsyncClient) -> None:
    await create_household(client)
    response = await client.post(
        "/households", json={"name": "Another"}, headers=auth("owner")
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_in_household"


async def test_blank_name_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/households", json={"name": "   "}, headers=auth("owner")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_member_joins_with_lowercase_code(
    client: AsyncClient, users: dict[str, AuthUser]
) -> None:
    household = await create_household(client)
    response = await client.post(
        "/households/join",
        json={"invite_code": household["invite_code"].lower()},
        headers=auth("member"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == household["id"]
    assert body["role"] == "member"
    assert {m["role"] for m in body["members"]} == {"owner", "member"}
    assert {m["email"] for m in body["members"]} == {
        users["owner"].email,
        users["member"].email,
    }


async def test_join_rejects_unknown_code(client: AsyncClient) -> None:
    response = await client.post(
        "/households/join", json={"invite_code": "ZZZZZZZZ"}, headers=auth("member")
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_invite_code"


async def test_join_rejects_a_full_household(
    client: AsyncClient, repo: FakeHouseholdsRepository
) -> None:
    household = await create_household(client)
    for _ in range(7):
        await repo.add_member(
            household_id=UUID(household["id"]),
            user_id=uuid4(),
            role="member",
        )

    response = await client.post(
        "/households/join",
        json={"invite_code": household["invite_code"]},
        headers=auth("outsider"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "household_full"
    assert await repo.count_members(UUID(household["id"])) == 8


async def test_outsider_cannot_read_a_household(
    client: AsyncClient,
) -> None:
    household = await create_household(client)

    without_header = await client.get("/households/me", headers=auth("outsider"))
    assert without_header.status_code == 404
    assert without_header.json()["error"]["code"] == "no_household"

    with_header = await client.get(
        "/households/me",
        headers={**auth("outsider"), "X-Household-Id": household["id"]},
    )
    assert with_header.status_code == 403
    assert with_header.json()["error"]["code"] == "not_a_member"


async def test_owner_can_use_household_header(client: AsyncClient) -> None:
    household = await create_household(client)
    response = await client.get(
        "/households/me",
        headers={**auth("owner"), "X-Household-Id": household["id"]},
    )
    assert response.status_code == 200


async def test_rotate_invite_changes_code_and_rotates_old_one(
    client: AsyncClient,
) -> None:
    household = await create_household(client)
    old_code = household["invite_code"]

    rotated = await client.post("/households/rotate-invite", headers=auth("owner"))
    assert rotated.status_code == 200
    new_code = rotated.json()["invite_code"]
    assert new_code != old_code

    stale = await client.post(
        "/households/join", json={"invite_code": old_code}, headers=auth("member")
    )
    assert stale.status_code == 404

    joined = await client.post(
        "/households/join", json={"invite_code": new_code}, headers=auth("member")
    )
    assert joined.status_code == 200


async def test_member_cannot_rotate_invite(client: AsyncClient) -> None:
    household = await create_household(client)
    await client.post(
        "/households/join",
        json={"invite_code": household["invite_code"]},
        headers=auth("member"),
    )

    response = await client.post("/households/rotate-invite", headers=auth("member"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_only"


async def test_member_cannot_create_a_second_household(client: AsyncClient) -> None:
    household = await create_household(client)
    await client.post(
        "/households/join",
        json={"invite_code": household["invite_code"]},
        headers=auth("member"),
    )
    response = await client.post(
        "/households", json={"name": "Second home"}, headers=auth("member")
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_in_household"


async def test_invalid_household_header_is_validation_error(client: AsyncClient) -> None:
    response = await client.get(
        "/households/me",
        headers={**auth("owner"), "X-Household-Id": "not-a-uuid"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
