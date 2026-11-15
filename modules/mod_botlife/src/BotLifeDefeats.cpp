#include "BotLifeDefeats.h"
#include "BotLife.h"
#include "Creature.h"
#include "Player.h"
#include "Playerbots.h"
#include "ScriptMgr.h"
#include "Timer.h"
#include "Log.h"
#include <mutex>
#include <unordered_map>
#include <algorithm>

namespace BotLife
{
namespace
{
struct Encounter
{
    DefeatArea area;
    std::vector<OpponentKey> participants;
    uint32_t at = 0;
};
struct BotMemory { DefeatHistory history; AreaDefeatHistory areas; Encounter encounter; uint32_t at = 0; };
std::mutex memoryMutex;
std::unordered_map<uint32_t, BotMemory> memories;

bool Eligible(Player* bot)
{
    if (!bot || !IsEligibleBot(bot->GetGUID().GetCounter()))
        return false;
    PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
    return ai && !ai->IsRealPlayer() && !ai->HasRealPlayerMaster() && !bot->InBattleground() && !bot->InArena();
}

DefeatPoint Position(Unit const& unit)
{
    return {unit.GetPositionX(), unit.GetPositionY(), unit.GetPositionZ()};
}

// Caller holds memoryMutex. Bound storage for damage observers as well as deaths.
BotMemory& Memory(uint32_t guid, uint32_t now)
{
    static uint32_t prunedAt = 0;
    if (uint32_t(now-prunedAt) >= 1000)
    {
        prunedAt = now;
        std::erase_if(memories, [now](auto const& row)
            { return uint32_t(now-row.second.at) >= DefeatHistory::LifetimeMs; });
    }
    if (!memories.count(guid) && memories.size() >= 1024)
    {
        auto oldest = memories.begin();
        for (auto it = memories.begin(); it != memories.end(); ++it)
            if (uint32_t(now-it->second.at) > uint32_t(now-oldest->second.at))
                oldest = it;
        memories.erase(oldest);
    }
    BotMemory& result = memories[guid];
    result.at = now;
    return result;
}

OpponentKey Key(Creature const& npc)
{
    // Spawn survives respawn; summoned creatures without a spawn use their
    // runtime GUID, never a shared template/entry as the sole identity.
    return {npc.GetMapId(), npc.GetInstanceId(), npc.GetEntry(),
        npc.GetSpawnId() ? uint64_t(npc.GetSpawnId()) : npc.GetGUID().GetRawValue(), npc.GetSpawnId() != 0};
}

class EncounterScript final : public UnitScript
{
public:
    EncounterScript() : UnitScript("BotLifeEncounterMemory") { }
    void OnDamage(Unit* attacker, Unit* victim, uint32& damage) override
    {
        if (!damage || !attacker || !victim)
            return;
        Player* bot = victim->ToPlayer();
        Creature* enemy = attacker->ToCreature();
        if (!bot || !enemy)
        {
            bot = attacker->ToPlayer();
            enemy = victim->ToCreature();
        }
        if (!enemy || !Eligible(bot) || !bot->IsAlive())
            return;
        uint32_t const now = getMSTime();
        std::lock_guard<std::mutex> lock(memoryMutex);
        Encounter& encounter = Memory(bot->GetGUID().GetCounter(), now).encounter;
        if (encounter.participants.empty() || !bot->IsInCombat() || uint32_t(now-encounter.at) >= 30000 ||
            encounter.area.map != bot->GetMapId() || encounter.area.instance != bot->GetInstanceId() ||
            encounter.area.phase != bot->GetPhaseMask())
        {
            encounter = {};
            // Anchor at the first actual opponent, not the ranged bot or a fleeing corpse.
            encounter.area = {bot->GetMapId(), bot->GetInstanceId(), bot->GetPhaseMask(), Position(*enemy)};
        }
        encounter.at = now;
        auto const key = Key(*enemy);
        if (encounter.participants.size() < 16 &&
            std::find(encounter.participants.begin(), encounter.participants.end(), key) == encounter.participants.end())
            encounter.participants.push_back(key);
    }
};

class DefeatMemoryScript final : public PlayerScript
{
public:
    DefeatMemoryScript() : PlayerScript("BotLifeDefeatMemory") { }
    void OnUpdate(Player* bot, uint32) override
    {
        if (!Eligible(bot) || bot->IsInCombat())
            return;
        std::lock_guard<std::mutex> lock(memoryMutex);
        auto it = memories.find(bot->GetGUID().GetCounter());
        if (it != memories.end())
            it->second.encounter = {}; // Do not carry a won fight into the next nearby fight.
    }
    void OnPlayerKilledByCreature(Creature* killer, Player* killed) override
    {
        if (!killer || !Eligible(killed))
            return;
        uint32_t const now = getMSTime(), guid = killed->GetGUID().GetCounter();
        uint32_t deaths, areaDeaths = 0;
        {
            std::lock_guard<std::mutex> lock(memoryMutex);
            BotMemory& memory = Memory(guid, now);
            deaths = memory.history.Record(Key(*killer), now);
            Encounter& encounter = memory.encounter;
            // No observed encounter means no invented camp around the corpse.
            if (!encounter.participants.empty() && uint32_t(now-encounter.at) < 30000 &&
                encounter.area.map == killed->GetMapId() && encounter.area.instance == killed->GetInstanceId() &&
                encounter.area.phase == killed->GetPhaseMask())
            {
                encounter.area.death = Position(*killed);
                areaDeaths = memory.areas.Record(encounter.area, now);
                TC_LOG_INFO("playerbots.botlife", "BotLife defeat-area guid={} deaths={} participants={} origin=({},{},{}) death=({},{},{}) radius=10 ttlMs=900000",
                    guid, areaDeaths, encounter.participants.size(), encounter.area.origin.x, encounter.area.origin.y,
                    encounter.area.origin.z, encounter.area.death.x, encounter.area.death.y, encounter.area.death.z);
            }
            encounter = {};
        }
        TC_LOG_INFO("playerbots.botlife", "BotLife defeat guid={} map={} instance={} spawn={} killer={} entry={} deaths={} avoid={} ttlMs={}",
            guid, killer->GetMapId(), killer->GetInstanceId(), killer->GetSpawnId(), killer->GetGUID().ToString(),
            killer->GetEntry(), deaths, deaths >= DefeatHistory::Threshold, DefeatHistory::LifetimeMs);
    }
    void OnLogout(Player* player) override
    {
        if (!player)
            return;
        std::lock_guard<std::mutex> lock(memoryMutex);
        memories.erase(player->GetGUID().GetCounter());
    }
};
}

bool AvoidDefeatedOpponent(Player const& bot, Creature const& enemy)
{
    if (!IsEligibleBot(bot.GetGUID().GetCounter()))
        return false;
    std::lock_guard<std::mutex> lock(memoryMutex);
    auto it = memories.find(bot.GetGUID().GetCounter());
    return it != memories.end() && it->second.history.Avoid(Key(enemy), getMSTime());
}

std::vector<DefeatArea> GetDefeatAreas(Player const& bot)
{
    if (!IsEligibleBot(bot.GetGUID().GetCounter()))
        return {};
    std::lock_guard<std::mutex> lock(memoryMutex);
    auto it = memories.find(bot.GetGUID().GetCounter());
    return it == memories.end() ? std::vector<DefeatArea>{} :
        it->second.areas.Active(bot.GetMapId(), bot.GetInstanceId(), bot.GetPhaseMask(), getMSTime());
}

void RegisterDefeatMemoryScript() { new DefeatMemoryScript(); new EncounterScript(); }
}
