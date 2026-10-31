#pragma once

#include "Common.h"

class PlayerbotAI;

namespace BattlegroundTest
{
    // Equal RandomBotMinLevel/MaxLevel selects one diagnostic BG bracket.
    // Zero leaves the ordinary level distribution in control.
    uint8 GetTargetLevel();

    // Optional diagnostic load lifecycle and telemetry. Objective behavior is
    // provided by ArathiBasinPlayerbot and is not test-mode-specific.
    void Update(uint32 diff);
}
