#!/usr/bin/env python3
"""Guard the production/test split of Arathi Basin playerbot behavior.

The full server build validates the real translation units. These assertions catch
accidental moves of objective behavior back into the opt-in load-test controller,
or bypasses of native queue, spell and battleground handlers.
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])

config = (root / "modules/mod_playerbots/src/Utils/PlayerbotAIConfig.cpp").read_text()
module = (root / "modules/mod_playerbots/src/mod_playerbots.cpp").read_text()
ai = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.cpp").read_text()
production = (root / "modules/mod_playerbots/src/Manager/ArathiBasinPlayerbot.cpp").read_text()
test_controller = (root / "modules/mod_playerbots/src/Manager/BattlegroundTestController.cpp").read_text()
release_spirit = (root / "modules/mod_playerbots/src/strategy/Dead/ReleaseSpiritAction.cpp").read_text()
auto_release = release_spirit[
    release_spirit.index("bool AutoReleaseSpiritAction::Execute"):
    release_spirit.index("bool AutoReleaseSpiritAction::isUseful")
]

for setting in (
    'GetBoolDefault("AiPlayerbot.RandomBotJoinBG", true)',
    'GetBoolDefault("AiPlayerbot.RandomBotAutoJoinBG", false)',
    'GetIntDefault("AiPlayerbot.RandomBotAutoJoinBGABCount", 1)',
    'GetStringDefault("AiPlayerbot.RandomBotAutoJoinABBrackets", "16")',
):
    assert setting in config, setting

assert "ArathiBasinPlayerbot::Update(diff)" in module
assert "BattlegroundTest::Update(diff)" in module
assert "ArathiBasinPlayerbot::DoNextAction(this)" in ai
assert "BattlegroundTest::DoNextAction" not in ai

for native_contract in (
    "HandleBattlemasterJoinOpcode(packet)",
    "HandleBattleFieldPortOpcode(packet)",
    "HandleBattlefieldLeaveOpcode(packet)",
    "bot->CastSpell(banner, OPENING_SPELL_ID, false)",
    "spell->m_targets.GetGOTargetGUID() == banner->GetGUID()",
    "FindFriendlyBannerCapturer(bot, banner, false)",
    "ApproachReserved(bot, state, x, y)",
    "lastMoveFailure == MoveFailure::Route",
):
    assert native_contract in production, native_contract

assert "EventPlayerClickedOnFlag" not in production
assert "TeleportTo(" not in production
assert "sPlayerbotAIConfig->battlegroundTest" in production

for lifecycle_contract in (
    "HandleBattlemasterJoinOpcode(packet)",
    "HandleBattleFieldPortOpcode(packet)",
    "HandleAreaSpiritHealerQueueOpcode(packet)",
    "HandleBattlefieldLeaveOpcode(packet)",
    "LogState(bot, state",
):
    assert lifecycle_contract in test_controller, lifecycle_contract

for objective_symbol in (
    "SelectObjective(",
    "ObjectiveMovement",
    "UseBanner(",
    "OPENING_SPELL_ID",
    "CastSpell(",
):
    assert objective_symbol not in test_controller, objective_symbol

assert 'AI_VALUE(GuidVector, "nearest npcs")' not in auto_release
assert "FindNearestCreature(entry" in auto_release
assert "HandleAreaSpiritHealerQueueOpcode(packet)" in auto_release

print("Arathi Basin production/test split regression passed")
