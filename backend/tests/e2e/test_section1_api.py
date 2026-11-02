from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import UserFactory, auth

pytestmark = pytest.mark.e2e


async def test_health_is_public(api_client: AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_protected_route_requires_a_token(api_client: AsyncClient) -> None:
    response = await api_client.get("/households/me")
    assert response.status_code == 401


async def test_create_join_and_isolation(
    api_client: AsyncClient,
    make_user: UserFactory,
) -> None:
    owner = await make_user("owner")
    member = await make_user("member")
    outsider = await make_user("outsider")

    created = await api_client.post(
        "/households", json={"name": "API E2E home"}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    household = created.json()
    code = household["invite_code"]

    joined = await api_client.post(
        "/households/join", json={"invite_code": code}, headers=auth(member)
    )
    assert joined.status_code == 200, joined.text
    assert len(joined.json()["members"]) == 2
    assert joined.json()["role"] == "member"

    member_rotate = await api_client.post("/households/rotate-invite", headers=auth(member))
    assert member_rotate.status_code == 403
    assert member_rotate.json()["error"]["code"] == "owner_only"

    owner_rotate = await api_client.post("/households/rotate-invite", headers=auth(owner))
    assert owner_rotate.status_code == 200
    assert owner_rotate.json()["invite_code"] != code

    stale_join = await api_client.post(
        "/households/join", json={"invite_code": code}, headers=auth(outsider)
    )
    assert stale_join.status_code == 404

    outsider_read = await api_client.get(
        "/households/me",
        headers={**auth(outsider), "X-Household-Id": household["id"]},
    )
    assert outsider_read.status_code == 403
    assert outsider_read.json()["error"]["code"] == "not_a_member"


async def test_member_cap(
    api_client: AsyncClient,
    make_user: UserFactory,
) -> None:
    owner = await make_user("cap-owner")
    members = [await make_user(f"cap-{index}") for index in range(7)]
    ninth = await make_user("cap-ninth")

    created = await api_client.post(
        "/households", json={"name": "Cap home"}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    code = created.json()["invite_code"]
    household_id = created.json()["id"]

    for member in members:
        response = await api_client.post(
            "/households/join", json={"invite_code": code}, headers=auth(member)
        )
        assert response.status_code == 200, response.text

    denied = await api_client.post(
        "/households/join", json={"invite_code": code}, headers=auth(ninth)
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "household_full"

    household = await api_client.get(
        "/households/me", headers={**auth(owner), "X-Household-Id": household_id}
    )
    assert household.status_code == 200
    assert len(household.json()["members"]) == 8
