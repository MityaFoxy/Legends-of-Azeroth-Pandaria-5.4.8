#pragma once

#include "Common.h"

class PlayerbotAI;

namespace BattlegroundTest
{
    // Optional diagnostic load lifecycle and telemetry. Objective behavior is
    // provided by ArathiBasinPlayerbot and is not test-mode-specific.
    void Update(uint32 diff);
}
