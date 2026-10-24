#pragma once

#include "Common.h"

namespace BattlegroundGraveyardRecovery
{
    // World-thread recovery for autonomous ghosts stranded outside a revive queue.
    void Update(uint32 diff);
}
