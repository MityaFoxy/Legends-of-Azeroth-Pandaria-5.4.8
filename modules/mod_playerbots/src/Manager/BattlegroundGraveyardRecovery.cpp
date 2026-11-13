#include "BattlegroundGraveyardRecovery.h"

#include "Player.h"
#include "Battleground.h"
#include "Creature.h"
#include "DBCStores.h"
#include "Log.h"
#include "Map.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "Playerbots.h"
#include "RandomPlayerbotMgr.h"
#include "Timer.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <cmath>
#include <map>
#include <set>

namespace
{
    constexpr uint32 RETURN_RETRY_MS = 10000;
    constexpr uint32 MAX_RETURN_ATTEMPTS = 3;
    constexpr float GRAVEYARD_ARRIVAL_DISTANCE = 20.0f;

    struct State
    {
        uint32 map = 0;
        uint32 instance = 0;
        uint32 team = 0;
        uint32 graveyard = 0;
        uint32 attempts = 0;
        uint32 lastRequest = 0;
        bool requested = false;
    };

    // Accessed only by the world-thread hook. No retained Player/Creature pointers.
    std::map<ObjectGuid, State> states;

    bool Eligible(Player* bot)
    {
        if (!bot || !bot->GetSession() || bot->GetSession()->isLogingOut())
            return false;
        PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
        return ai && !ai->IsRealPlayer() && !ai->HasRealPlayerMaster()
            && sPlayerbotAIConfig->IsInRandomAccountList(bot->GetSession()->GetAccountId())
            && !bot->IsAlive() && bot->HasPlayerFlag(PLAYER_FLAGS_GHOST);
    }

    bool Recover(Player* bot, State& state, uint32 now)
    {
        if (!Eligible(bot) || !bot->IsInWorld() || bot->IsBeingTeleported())
            return false;
        Battleground* bg = bot->GetBattleground();
        if (!bg || bg->IsArena() || bg->IsRated() || bg->GetStatus() != STATUS_IN_PROGRESS)
            return false;
        Map* map = bg->FindBgMap();
        if (!map || bot->GetMap() != map || bot->GetInstanceId() != bg->GetInstanceID())
            return false;

        if (state.map != bot->GetMapId() || state.instance != bg->GetInstanceID() || state.team != bot->GetBGTeam())
        {
            state = State{};
            state.map = bot->GetMapId();
            state.instance = bg->GetInstanceID();
            state.team = bot->GetBGTeam();
        }

        // A valid queue/visual-delay stage belongs to the native resurrection wave.
        if (bot->HasAura(SPELL_WAITING_FOR_RESURRECT))
            return false;
        uint32 entry = bot->GetBGTeam() == ALLIANCE
            ? BG_CREATURE_ENTRY_A_SPIRITGUIDE : BG_CREATURE_ENTRY_H_SPIRITGUIDE;
        Creature* guide = bot->FindNearestCreature(entry, sPlayerbotAIConfig->sightDistance, true);
        if (!guide)
            guide = bot->FindNearestCreature(entry, sPlayerbotAIConfig->sightDistance, false);
        if (guide && guide->IsSpiritService())
            return false; // Existing dead AI approaches and queues at this guide.

        // RepopAtGraveyard also has emergency direct-resurrection branches. This
        // recovery must not invoke those for transports, deep falls or flight-only areas.
        AreaTableEntry const* area = sAreaTableStore.LookupEntry(bot->GetAreaId());
        if (!area || (area->Flags & AREA_FLAG_NEED_FLY) || bot->GetTransport()
            || !std::isfinite(bot->GetPositionZ()) || bot->GetPositionZ() < area->MaxDepth)
            return false;

        WorldSafeLocsEntry const* grave = bg->GetClosestGraveYard(bot);
        if (!grave || grave->map_id != bot->GetMapId() || !std::isfinite(grave->x)
            || !std::isfinite(grave->y) || !std::isfinite(grave->z))
            return false;
        float distance = bot->GetExactDist(grave->x, grave->y, grave->z);
        if (!std::isfinite(distance) || distance <= GRAVEYARD_ARRIVAL_DISTANCE)
            return false; // Already at the selected grave: never teleport in place.
        if (state.requested && getMSTimeDiff(state.lastRequest, now) < RETURN_RETRY_MS)
            return false; // Also throttle rapidly changing destinations.
        if (state.graveyard != grave->ID)
        {
            state.graveyard = grave->ID;
            state.attempts = 0;
        }
        if (state.attempts >= MAX_RETURN_ATTEMPTS)
            return false;

        state.lastRequest = now;
        state.requested = true;
        ++state.attempts;
        // Same world-thread request as a player's "Return to Graveyard" button.
        // Do not force resurrection, remove auras, or manually insert queue entries.
        WorldPacket packet(CMSG_RETURN_TO_GRAVEYARD);
        bot->GetSession()->HandleReturnToGraveyard(packet);
        TC_LOG_INFO("bg.resurrection", "BG graveyard-return GUID={} map={} instance={} graveyard={} attempt={}",
            bot->GetGUID().GetCounter(), state.map, state.instance, state.graveyard, state.attempts);
        return true;
    }
}

void BattlegroundGraveyardRecovery::Update(uint32 diff)
{
    static uint32 elapsed = 0;
    elapsed += diff;
    if (elapsed < 1000)
        return;
    elapsed = 0;

    uint32 now = getMSTime();
    std::set<ObjectGuid> active;
    for (auto itr = sRandomPlayerbotMgr->GetPlayerBotsBegin(); itr != sRandomPlayerbotMgr->GetPlayerBotsEnd(); ++itr)
    {
        Player* bot = itr->second;
        if (!Eligible(bot) || !bot->GetBattleground())
            continue;
        active.insert(bot->GetGUID());
        Recover(bot, states[bot->GetGUID()], now);
    }
    for (auto itr = states.begin(); itr != states.end();)
    {
        if (!active.count(itr->first))
            itr = states.erase(itr);
        else
            ++itr;
    }
}
