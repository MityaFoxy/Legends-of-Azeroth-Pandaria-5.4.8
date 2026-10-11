#pragma once

#include "Common.h"

class PlayerbotAI;

namespace BattlegroundTest
{
    // World-thread only: native queue, invite, resurrection and banner cast.
    void Update(uint32 diff);
    // Map-thread AI action: normal navigation/PvP AI, never global queue mutation.
    bool DoNextAction(PlayerbotAI* ai);
}
