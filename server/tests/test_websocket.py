"""Integration tests for the /ws endpoint.

Uses Starlette's TestClient (via fastapi.testclient) — httpx.AsyncClient
does not support WebSockets. The tests register accounts + characters over
HTTP through the same client, then drive the WS protocol directly.

Coverage:
  - auth rejection (missing / invalid token)
  - welcome message on connect
  - BAD_PAYLOAD survival (regression for the "below" direction crash)
  - look (no target, target item, not found)
  - move success + room.entered
  - take/drop round trip; take twice returns TAKE_NOT_FOUND
  - take race between two players: exactly one wins
  - say is room-scoped; shout is global; presence fan-out on move
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

pytestmark = pytest.mark.integration


# ---- helpers ----

PASSWORD = "test-password-12345"


def _register_and_create(tc: TestClient, email: str, name: str) -> str:
    """Register an account and create a character. Returns the access token."""
    r = tc.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    token = r.json()["accessToken"]
    r = tc.post(
        "/characters",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return token


def _drain_welcome(ws: WebSocketTestSession) -> dict[str, Any]:
    msg = ws.receive_json()
    assert msg["type"] == "server.welcome"
    return msg


# ---- auth ----

def test_ws_rejects_missing_token(sync_client: TestClient) -> None:
    # The endpoint closes with policy violation before accepting; TestClient
    # surfaces this as a WebSocketDisconnect when the body tries to read.
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_ws_rejects_invalid_token(sync_client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/ws?token=not-a-real-jwt") as ws:
            ws.receive_json()


# ---- welcome + ping ----

def test_welcome_describes_starting_room(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        msg = _drain_welcome(ws)
        assert msg["data"]["player"]["name"] == "Ada"
        room = msg["data"]["room"]
        assert room["id"] == "town-square"
        assert any(e["direction"] == "north" for e in room["exits"])
        assert any(item["id"] == "rusty-key" for item in room["items"])


def test_ping_returns_pong(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)
        ws.send_json({"type": "client.ping"})
        msg = ws.receive_json()
        assert msg["type"] == "server.pong"


# ---- validation regression ----

def test_invalid_direction_returns_error_and_keeps_socket_alive(
    sync_client: TestClient,
) -> None:
    """Regression: ``below`` is not a valid Direction. Before the fix, the
    Pydantic ValidationError propagated out and Starlette closed the socket."""
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)

        ws.send_json({"type": "client.command.move", "data": {"direction": "below"}})
        err = ws.receive_json()
        assert err["type"] == "server.error"
        assert err["data"]["code"] == "BAD_PAYLOAD"
        assert "direction" in err["data"]["message"]

        # Socket survives — ping still works.
        ws.send_json({"type": "client.ping"})
        pong = ws.receive_json()
        assert pong["type"] == "server.pong"


# ---- look ----

def test_look_with_no_target_returns_room_view(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)
        ws.send_json({"type": "client.command.look"})
        msg = ws.receive_json()
        assert msg["type"] == "server.room.entered"
        assert msg["data"]["id"] == "town-square"


def test_look_at_item_returns_examine_result(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)
        ws.send_json({"type": "client.command.look", "data": {"target": "rusty key"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.examine.result"
        assert msg["data"]["kind"] == "item"
        assert msg["data"]["name"] == "rusty key"


def test_look_at_missing_target_returns_error(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)
        ws.send_json({"type": "client.command.look", "data": {"target": "banana"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.error"
        assert msg["data"]["code"] == "LOOK_NOT_FOUND"


# ---- move ----

def test_move_north_then_south_round_trip(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)

        ws.send_json({"type": "client.command.move", "data": {"direction": "north"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.room.entered"
        assert msg["data"]["id"] == "north-road"

        ws.send_json({"type": "client.command.move", "data": {"direction": "south"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.room.entered"
        assert msg["data"]["id"] == "town-square"


def test_move_with_no_exit_returns_error(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)
        # Town square has no south exit in the seed data.
        ws.send_json({"type": "client.command.move", "data": {"direction": "south"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.error"
        assert msg["data"]["code"] == "NO_EXIT"


# ---- take / drop ----

def test_take_then_drop_round_trip(sync_client: TestClient) -> None:
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)

        ws.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.inventory.updated"
        assert [it["id"] for it in msg["data"]["items"]] == ["rusty-key"]

        # Taking it again should fail; nobody else cleared the room first.
        ws.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.error"
        assert msg["data"]["code"] == "TAKE_NOT_FOUND"

        ws.send_json({"type": "client.command.drop", "data": {"target": "rusty key"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.inventory.updated"
        assert msg["data"]["items"] == []

        # And dropping again fails because we're no longer carrying it.
        ws.send_json({"type": "client.command.drop", "data": {"target": "rusty key"}})
        msg = ws.receive_json()
        assert msg["type"] == "server.error"
        assert msg["data"]["code"] == "DROP_NOT_FOUND"


def test_concurrent_take_only_one_wins(sync_client: TestClient) -> None:
    """Two players both attempt to take the rusty key. The conditional `$pull`
    against ``rooms.itemIds`` ensures exactly one succeeds — the other sees
    ``TAKE_NOT_FOUND`` because the item is no longer in the room."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        # Queue both takes back-to-back without reading responses in between.
        # Server still processes them serially against Mongo; the first take
        # wins the $pull and the second falls through to TAKE_NOT_FOUND.
        a.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        b.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})

        msg_a = a.receive_json()
        msg_b = b.receive_json()
        types = sorted([msg_a["type"], msg_b["type"]])
        assert types == ["server.error", "server.inventory.updated"]

        loser = msg_a if msg_a["type"] == "server.error" else msg_b
        assert loser["data"]["code"] == "TAKE_NOT_FOUND"


# ---- broker fan-out: presence + chat ----

def test_say_is_scoped_to_room(sync_client: TestClient) -> None:
    """Two players in the same room both see a say; after one moves away the
    other no longer receives their sayings."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        a.send_json({"type": "client.command.say", "data": {"message": "hello"}})

        # Both should receive — the sender included in the fan-out for
        # self-echo confirmation.
        msg_a = a.receive_json()
        msg_b = b.receive_json()
        for msg in (msg_a, msg_b):
            assert msg["type"] == "server.chat.say"
            assert msg["data"]["from"] == "Anna"
            assert msg["data"]["message"] == "hello"


def test_move_broadcasts_departed_and_arrived(sync_client: TestClient) -> None:
    """When Anna walks north, Beth (in town-square) sees ``server.player.departed``;
    the inverse direction is what Anna would have observed had she been the
    one staying behind."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        a.send_json({"type": "client.command.move", "data": {"direction": "north"}})

        # Anna receives room.entered for the destination.
        msg_a = a.receive_json()
        assert msg_a["type"] == "server.room.entered"
        assert msg_a["data"]["id"] == "north-road"

        # Beth receives departed with the mover's chosen direction.
        msg_b = b.receive_json()
        assert msg_b["type"] == "server.player.departed"
        assert msg_b["data"]["playerName"] == "Anna"
        assert msg_b["data"]["toDirection"] == "north"


def test_arrived_fromDirection_is_observers_viewpoint(sync_client: TestClient) -> None:
    """A second player in the destination room should see Anna arrive from
    the opposite of Anna's chosen direction."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        # Beth walks to north-road first so she'll be there when Anna arrives.
        b.send_json({"type": "client.command.move", "data": {"direction": "north"}})
        msg = b.receive_json()
        assert msg["type"] == "server.room.entered"
        # Anna (still in town-square) sees Beth's departure.
        anna_sees_beth_leave = a.receive_json()
        assert anna_sees_beth_leave["type"] == "server.player.departed"

        # Now Anna walks north too.
        a.send_json({"type": "client.command.move", "data": {"direction": "north"}})

        # Anna gets room.entered.
        msg_a = a.receive_json()
        assert msg_a["type"] == "server.room.entered"

        # Beth (in north-road) sees Anna arrive from the south.
        msg_b = b.receive_json()
        assert msg_b["type"] == "server.player.arrived"
        assert msg_b["data"]["playerName"] == "Anna"
        assert msg_b["data"]["fromDirection"] == "south"


def test_shout_reaches_players_in_other_rooms(sync_client: TestClient) -> None:
    """Global chat: Beth moves to a different room, Anna shouts, Beth still
    receives it — say wouldn't have crossed the room boundary."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        # Beth walks to north-road; Anna sees the departed event.
        b.send_json({"type": "client.command.move", "data": {"direction": "north"}})
        b.receive_json()  # room.entered for Beth
        a.receive_json()  # departed for Anna's view

        a.send_json({"type": "client.command.shout", "data": {"message": "anyone there"}})

        msg_a = a.receive_json()
        msg_b = b.receive_json()
        for msg in (msg_a, msg_b):
            assert msg["type"] == "server.chat.shout"
            assert msg["data"]["from"] == "Anna"
            assert msg["data"]["message"] == "anyone there"


# ---- who ----

def test_who_solo_returns_just_self(sync_client: TestClient) -> None:
    """A single connected player should see only themselves in the who list."""
    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with sync_client.websocket_connect(f"/ws?token={token}") as ws:
        _drain_welcome(ws)

        ws.send_json({"type": "client.command.who"})
        msg = ws.receive_json()

        assert msg["type"] == "server.who.list"
        assert msg["data"]["players"] == ["Ada"]


def test_who_lists_all_connected_players(sync_client: TestClient) -> None:
    """When two players are online (anywhere in the world), both names
    appear in the who list, sorted case-insensitively."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        a.send_json({"type": "client.command.who"})
        msg = a.receive_json()

        assert msg["type"] == "server.who.list"
        assert msg["data"]["players"] == ["Anna", "Beth"]


def test_who_does_not_count_disconnected_characters(sync_client: TestClient) -> None:
    """A character whose owner has never connected (or has disconnected)
    should not appear in the online list — the broker tracks live sockets,
    not the players collection."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    _register_and_create(sync_client, "ghost@test.com", "Ghost")  # never connects

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a:
        _drain_welcome(a)

        a.send_json({"type": "client.command.who"})
        msg = a.receive_json()

        assert msg["type"] == "server.who.list"
        assert msg["data"]["players"] == ["Anna"]


# ---- quit ----

def test_quit_closes_the_socket_cleanly(sync_client: TestClient) -> None:
    """client.command.quit should result in a normal-closure (1000) WS close.

    The pytest.raises wraps the entire websocket_connect block so the
    WebSocketDisconnect propagates through Starlette's test-session
    __exit__ — catching it inside would let __exit__ attempt a second
    close() on the closed session and raise a follow-up RuntimeError.
    Same pattern as the auth-rejection tests above.
    """
    from starlette.websockets import WebSocketDisconnect

    token = _register_and_create(sync_client, "ada@test.com", "Ada")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(f"/ws?token={token}") as ws:
            _drain_welcome(ws)
            ws.send_json({"type": "client.command.quit"})
            ws.receive_json()  # should not return; raises WebSocketDisconnect

    assert exc_info.value.code == 1000


# ---- broker fan-out: item events ----

def test_take_broadcasts_item_taken_to_others_in_room(sync_client: TestClient) -> None:
    """When Anna takes the rusty key, Beth (also in town-square) sees a
    server.item.taken with the actor name + item name. Anna herself only
    gets server.inventory.updated."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        a.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})

        msg_a = a.receive_json()
        assert msg_a["type"] == "server.inventory.updated"
        assert [it["id"] for it in msg_a["data"]["items"]] == ["rusty-key"]

        msg_b = b.receive_json()
        assert msg_b["type"] == "server.item.taken"
        assert msg_b["data"]["playerName"] == "Anna"
        assert msg_b["data"]["itemName"] == "rusty key"


def test_drop_broadcasts_item_dropped_to_others_in_room(sync_client: TestClient) -> None:
    """After a take/drop pair, the second observer sees taken then dropped
    in order."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        # Take first; drain the corresponding events on both sides.
        a.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        assert a.receive_json()["type"] == "server.inventory.updated"
        assert b.receive_json()["type"] == "server.item.taken"

        # Now the drop.
        a.send_json({"type": "client.command.drop", "data": {"target": "rusty key"}})

        msg_a = a.receive_json()
        assert msg_a["type"] == "server.inventory.updated"
        assert msg_a["data"]["items"] == []

        msg_b = b.receive_json()
        assert msg_b["type"] == "server.item.dropped"
        assert msg_b["data"]["playerName"] == "Anna"
        assert msg_b["data"]["itemName"] == "rusty key"


def test_actor_does_not_receive_own_item_event(sync_client: TestClient) -> None:
    """The actor's only response to take is server.inventory.updated; the
    broker fan-out excludes them so they don't get a redundant
    server.item.taken about themselves. Verified by sending a ping and
    asserting the next frame is pong — if a stray item.taken were queued,
    it would arrive first."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a:
        _drain_welcome(a)

        a.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        assert a.receive_json()["type"] == "server.inventory.updated"

        a.send_json({"type": "client.ping"})
        assert a.receive_json()["type"] == "server.pong"


def test_item_event_does_not_cross_rooms(sync_client: TestClient) -> None:
    """Beth moves to north-road, then Anna takes the key in town-square.
    Beth should not receive server.item.taken — the broker fan-out is
    room-scoped. Verified by ping/pong ordering on Beth's socket."""
    a_token = _register_and_create(sync_client, "anna@test.com", "Anna")
    b_token = _register_and_create(sync_client, "beth@test.com", "Beth")

    with sync_client.websocket_connect(f"/ws?token={a_token}") as a, \
         sync_client.websocket_connect(f"/ws?token={b_token}") as b:
        _drain_welcome(a)
        _drain_welcome(b)

        # Beth leaves town-square; drain the presence events on both sides.
        b.send_json({"type": "client.command.move", "data": {"direction": "north"}})
        assert b.receive_json()["type"] == "server.room.entered"
        assert a.receive_json()["type"] == "server.player.departed"

        # Anna takes the key in town-square. Beth is no longer there.
        a.send_json({"type": "client.command.take", "data": {"target": "rusty key"}})
        assert a.receive_json()["type"] == "server.inventory.updated"

        # If Beth had received server.item.taken it would be queued ahead
        # of her pong — confirm the next frame is the pong.
        b.send_json({"type": "client.ping"})
        assert b.receive_json()["type"] == "server.pong"
