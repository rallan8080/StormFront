"""Unit tests for app.broker.Broker.

These exercise the in-process pub/sub directly with a fake WebSocket — no
HTTP, no DB. They cover the invariants the WS endpoint relies on:
  - connect/disconnect lifecycle
  - newer-wins reconnect (displaced socket gets closed, its later
    disconnect call is a no-op)
  - move() rewires room membership atomically
  - publish_to_room respects exclude_player_id and only reaches members
  - publish_to_all reaches every connected player regardless of room
  - one broken socket in a fan-out doesn't break delivery to the others
"""
from __future__ import annotations

import pytest

from app.broker import Broker

pytestmark = pytest.mark.unit


class FakeWebSocket:
    """Stand-in for fastapi.WebSocket. Records sent text; can simulate breakage."""

    def __init__(self, *, fail_send: bool = False) -> None:
        self.sent: list[str] = []
        self.closed: bool = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self._fail_send = fail_send

    async def send_text(self, text: str) -> None:
        if self._fail_send or self.closed:
            raise RuntimeError("socket broken")
        self.sent.append(text)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class FakePayload:
    """Duck-typed pydantic message: only ``model_dump_json`` is consumed by Broker."""

    def __init__(self, value: str) -> None:
        self.value = value

    def model_dump_json(self, by_alias: bool = False) -> str:
        return f'{{"value":"{self.value}"}}'


async def test_connect_then_publish_reaches_socket() -> None:
    broker = Broker()
    ws = FakeWebSocket()
    await broker.connect("p1", ws, "room-A")

    await broker.publish_to_room("room-A", FakePayload("hello"))

    assert ws.sent == ['{"value":"hello"}']


async def test_disconnect_stops_subsequent_delivery() -> None:
    broker = Broker()
    ws = FakeWebSocket()
    await broker.connect("p1", ws, "room-A")
    await broker.disconnect("p1", ws)

    await broker.publish_to_room("room-A", FakePayload("ignored"))

    assert ws.sent == []


async def test_reconnect_displaces_old_socket() -> None:
    broker = Broker()
    old = FakeWebSocket()
    new = FakeWebSocket()

    await broker.connect("p1", old, "room-A")
    await broker.connect("p1", new, "room-A")

    assert old.closed
    assert old.close_code == 1000
    assert "Replaced" in (old.close_reason or "")
    assert not new.closed


async def test_displaced_socket_disconnect_is_noop() -> None:
    """If the displaced socket's own disconnect runs after a reconnect, it must
    not unregister the new socket — otherwise reconnect orphans the player."""
    broker = Broker()
    old = FakeWebSocket()
    new = FakeWebSocket()

    await broker.connect("p1", old, "room-A")
    await broker.connect("p1", new, "room-A")
    await broker.disconnect("p1", old)  # late teardown from the displaced coroutine

    await broker.publish_to_room("room-A", FakePayload("still here"))

    assert new.sent == ['{"value":"still here"}']


async def test_move_rewires_room_membership() -> None:
    broker = Broker()
    a = FakeWebSocket()
    b = FakeWebSocket()
    await broker.connect("ada", a, "town-square")
    await broker.connect("bob", b, "town-square")

    # Both members of town-square initially.
    await broker.publish_to_room("town-square", FakePayload("everyone"))
    assert len(a.sent) == 1
    assert len(b.sent) == 1

    await broker.move("ada", "north-road")

    # Town-square delivery should now only reach Bob.
    await broker.publish_to_room("town-square", FakePayload("bob only"))
    assert len(a.sent) == 1
    assert b.sent[-1] == '{"value":"bob only"}'

    # And Ada is reachable in the new room.
    await broker.publish_to_room("north-road", FakePayload("ada only"))
    assert a.sent[-1] == '{"value":"ada only"}'
    assert len(b.sent) == 2


async def test_publish_to_room_exclude_player_id() -> None:
    broker = Broker()
    a = FakeWebSocket()
    b = FakeWebSocket()
    await broker.connect("ada", a, "town-square")
    await broker.connect("bob", b, "town-square")

    await broker.publish_to_room(
        "town-square", FakePayload("from-ada"), exclude_player_id="ada",
    )

    assert a.sent == []
    assert b.sent == ['{"value":"from-ada"}']


async def test_publish_to_all_reaches_every_room() -> None:
    broker = Broker()
    a = FakeWebSocket()
    b = FakeWebSocket()
    c = FakeWebSocket()
    await broker.connect("ada", a, "town-square")
    await broker.connect("bob", b, "north-road")
    await broker.connect("eve", c, "east-market")

    await broker.publish_to_all(FakePayload("global"))

    assert a.sent == ['{"value":"global"}']
    assert b.sent == ['{"value":"global"}']
    assert c.sent == ['{"value":"global"}']


async def test_one_broken_socket_does_not_break_fanout() -> None:
    broker = Broker()
    ok = FakeWebSocket()
    broken = FakeWebSocket(fail_send=True)
    await broker.connect("ada", ok, "town-square")
    await broker.connect("bob", broken, "town-square")

    # Should not raise even though one send fails.
    await broker.publish_to_room("town-square", FakePayload("test"))

    assert ok.sent == ['{"value":"test"}']
    assert broken.sent == []


async def test_publish_to_empty_room_is_noop() -> None:
    broker = Broker()
    # No connections at all.
    await broker.publish_to_room("ghost-room", FakePayload("anyone there?"))
    await broker.publish_to_all(FakePayload("hello?"))
    # Just asserting it doesn't raise; nothing to receive against.


async def test_move_to_same_room_is_idempotent() -> None:
    broker = Broker()
    ws = FakeWebSocket()
    await broker.connect("p1", ws, "room-A")

    await broker.move("p1", "room-A")  # noop

    await broker.publish_to_room("room-A", FakePayload("still here"))
    assert ws.sent == ['{"value":"still here"}']
