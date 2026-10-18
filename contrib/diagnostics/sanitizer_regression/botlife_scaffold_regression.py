#!/usr/bin/env python3
"""Guard the optional, non-invasive first BotLife layer."""

import pathlib
import sys


root = pathlib.Path(sys.argv[1])
options = (root / "cmake/options.cmake").read_text()
modules_cmake = (root / "modules/CMakeLists.txt").read_text()
config = (root / "modules/mod_botlife/config/botlife.conf.dist").read_text()
config_cpp = (root / "modules/mod_playerbots/src/Utils/PlayerbotAIConfig.cpp").read_text()
ai = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.cpp").read_text()
ai_header = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.h").read_text()
extension = (root / "modules/mod_playerbots/src/AI/PlayerbotAIExtension.h").read_text()
module = (root / "modules/mod_botlife/src/mod_botlife.cpp").read_text()
header = (root / "modules/mod_botlife/src/BotLife.h").read_text()
implementation = (root / "modules/mod_botlife/src/BotLife.cpp").read_text()
activity = (root / "modules/mod_botlife/src/BotLifeActivity.cpp").read_text()

assert 'option(BOTLIFE          "Build optional BotLife layer for playerbots"                 0)' in options
assert 'list(REMOVE_ITEM VALID_MODULES "mod_botlife")' in modules_cmake
assert 'message(FATAL_ERROR "BOTLIFE requires PLAYERBOTS")' in modules_cmake
assert 'set(MODULES_LOADER_GENERATED "${CMAKE_CURRENT_BINARY_DIR}/ModulesLoader.cpp")' in modules_cmake
assert "execute_process(COMMAND ${CMAKE_COMMAND} -E copy_if_different" not in modules_cmake
assert "[botlife]" in config
assert "AiPlayerbot.BotLife.Enabled = 0" in config
assert "AiPlayerbot.BotLife.BotGuids =" in config
assert 'GetBoolDefault("AiPlayerbot.BotLife.Enabled", false)' in implementation
assert 'GetStringDefault("AiPlayerbot.BotLife.BotGuids", "")' in implementation
assert "BotLife" not in config_cpp

assert "BotLife" not in ai
assert "BotLife" not in ai_header
assert "class PlayerbotAIExtension" in extension
assert "SuppressBaseNonCombatAction" in extension
assert "sPlayerbotAIExtensionRegistry->Register(&CreateBotLifeExtension)" in module

for activity in ("Free", "Quest", "Town", "Rest"):
    assert activity in header, activity
for result in ("Running", "Completed", "TemporarilyBlocked", "Failed"):
    assert result in header, result
for operation in ("Start", "Update", "Pause", "Resume", "Interrupt", "Finish", "Observe"):
    assert f" {operation}(" in header, operation

update = ai[ai.index("void PlayerbotAI::UpdateAIInternal"):ai.index("bool PlayerbotAI::DoSpecificAction")]
assert update.index("extension->Update(*this, elapsed)") < update.index("DoNextAction(minimal)")
assert "if (runBaseAI)" in update
assert "_currentState == BOT_STATE_NON_COMBAT" in update
assert "bot->IsAlive() && !bot->IsInCombat()" in update
early_update = ai[ai.index("void PlayerbotAI::UpdateAI("):ai.index("void PlayerbotAI::UpdateAIInternal")]
assert early_update.index("extension->Observe(*this)") < early_update.index("if (nextAICheckDelay")
teleport = ai[ai.index("void PlayerbotAI::HandleTeleportAck()"):ai.index("void PlayerbotAI::HandleBotOutgoingPacket")]
assert teleport.index("extension->Observe(*this)") < teleport.index("bot->GetMotionMaster()->Clear")
reset = ai[ai.index("void PlayerbotAI::Reset(bool full)"):ai.index("void PlayerbotAI::ResetStrategies")]
assert "extension->Reset(*this)" in reset
destructor = ai[ai.index("PlayerbotAI::~PlayerbotAI()") : ai.index("uint32 PlayerbotAI::GetReactDelay")]
assert "extension->Reset(*this)" in destructor
assert "HasRealPlayerMaster()" in implementation
assert "IsEligible(" in implementation
assert "duration_ms={}" in implementation
assert "return PlayerbotAIExtensionResult::ContinueBaseAI" in implementation

for forbidden in (
    "TeleportTo(",
    "MovePoint(",
    "PathGenerator",
    "KilledMonsterCredit(",
    "CompleteQuest(",
    "RewardQuest(",
    "Attack(",
):
    assert forbidden not in implementation + activity, f"BotLife lifecycle scaffold became invasive: {forbidden}"

assert len(implementation.splitlines()) < 300, "BotLife.cpp is becoming a monolith; split the next executor"

print("BotLife optional layer contract passed")
