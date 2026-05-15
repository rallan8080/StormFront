"""Unit tests for app.npc_scheduler.NpcScheduler.

The scheduler's tick body — ``fire_once`` — is the interesting piece:
it picks a random NPC/line and pushes a server.npc.spoke through the
broker. We drive it directly so the test doesn't have to wait for the
random sleep in _chatter_loop. The loop itself is straightforward
sleep+call+except, covered by inspection.
"""
from __future__ import annotations

import json

import pytest

from app.broker import Broker
from app.npc_scheduler import NpcScheduler

pytestmark = pytest.mark.unit


class FakeWebSocket:
    """Minimal stand-in for fastapi.WebSocket — same shape used in
    test_broker.py. Duplicated rather than shared to keep test files
    self-contained."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed: bool = False

    async def send_text(self, text: str) -> None:
        if self.closed:
            raise RuntimeError("socket closed")
        self.sent.append(text)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


def _make_scheduler() -> NpcScheduler:
    # db argument is unused by fire_once; pass None and tell type-checker
    # we know what we're doing.
    return NpcScheduler(db=None, broker=Broker())  # type: ignore[arg-type]


async def test_fire_once_publishes_npc_spoke_to_room_members() -> None:
    scheduler = _make_scheduler()
    listener = FakeWebSocket()
    await scheduler._broker.connect("ada", listener, "town-square")

    npcs = [{"name": "town crier", "dialogue": ["Hear ye!"]}]
    await scheduler.fire_once("town-square", npcs)

    assert len(listener.sent) == 1
    payload = json.loads(listener.sent[0])
    assert payload["type"] == "server.npc.spoke"
    assert payload["data"]["npcName"] == "town crier"
    assert payload["data"]["message"] == "Hear ye!"


async def test_fire_once_picks_a_line_from_the_chosen_npc() -> None:
    """Whatever line gets picked, it must come from that NPC's dialogue."""
    scheduler = _make_scheduler()
    listener = FakeWebSocket()
    await scheduler._broker.connect("ada", listener, "town-square")

    lines = ["one", "two", "three"]
    npcs = [{"name": "town crier", "dialogue": lines}]
    await scheduler.fire_once("town-square", npcs)

    payload = json.loads(listener.sent[0])
    assert payload["data"]["message"] in lines


async def test_fire_once_with_no_speakable_npcs_is_silent() -> None:
    """NPCs with empty (or missing) dialogue shouldn't produce a frame."""
    scheduler = _make_scheduler()
    listener = FakeWebSocket()
    await scheduler._broker.connect("ada", listener, "town-square")

    await scheduler.fire_once("town-square", [{"name": "mute", "dialogue": []}])
    await scheduler.fire_once("town-square", [{"name": "mute"}])  # no dialogue key
    await scheduler.fire_once("town-square", [])  # no NPCs at all

    assert listener.sent == []


async def test_fire_once_does_not_send_to_other_rooms() -> None:
    """Room-scoped publish: only members of the named room receive."""
    scheduler = _make_scheduler()
    here = FakeWebSocket()
    elsewhere = FakeWebSocket()
    await scheduler._broker.connect("ada", here, "town-square")
    await scheduler._broker.connect("bob", elsewhere, "north-road")

    await scheduler.fire_once(
        "town-square", [{"name": "town crier", "dialogue": ["Hi"]}],
    )

    assert len(here.sent) == 1
    assert elsewhere.sent == []


async def test_constructor_rejects_invalid_intervals() -> None:
    broker = Broker()
    with pytest.raises(ValueError):
        NpcScheduler(db=None, broker=broker, min_interval=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        NpcScheduler(db=None, broker=broker, min_interval=10, max_interval=5)  # type: ignore[arg-type]
