#!/usr/bin/env python3
"""Verify Playerbot level balancing follows the actual MoP BG brackets."""

from pathlib import Path
import re
import sys


root = Path(sys.argv[1])
source = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotBracketMgr.cpp").read_text()
header = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotBracketMgr.h").read_text()
controller = (root / "modules/mod_playerbots/src/Manager/BattlegroundTestController.cpp").read_text()
world_config = (root / "src/server/worldserver/worldserver.conf.dist").read_text()

ranges = [
    tuple(map(int, match))
    for match in re.findall(
        r"_AllianceLevelRanges\[\d+\]\s*=\s*\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}",
        source,
    )
]

expected_bounds = [(1, 9)] + [(level, level + 4) for level in range(10, 90, 5)] + [(90, 90)]
assert [(low, high) for low, high, _ in ranges] == expected_bounds
assert sum(percent for _, _, percent in ranges) == 100
assert "NUM_RANGES = 18" in header

# The current 500-bot workload is approximately 250 bots per faction. Every
# real AB bracket must receive at least its native eight-player minimum after
# distribution, even before cross-faction balancing is considered.
for low, _, percent in ranges:
    if low >= 10:
        assert round(percent * 250 / 100) >= 8

assert "_BotDistCheckFrequency = 30" in header
assert "_BotDistDebugMode{ false }" in source
assert "!CanPlayerLeaveStartingArea(player)" in source
assert "effectiveLevel = targetLevel" in source
assert "!pendingRandomization && !player->InBattleground()" in source
assert "!player->InBattlegroundQueue()" in source
locked_log = controller.index('LogState(bot, state, "starting-area-locked", now)')
normal_log = controller.index('LogState(bot, state, state.finished ? "rejoin" : "online", now)')
assert locked_log < normal_log
assert "if (!state.initialQueueDelayStarted)" in controller
assert "state.initialQueueDelayStarted = true" in controller
assert "MarkRequest(state, now)" in controller
assert "Battleground.QueueAnnouncer.Enable = 0" in world_config
assert "Arena.QueueAnnouncer.Enable = 0" in world_config
