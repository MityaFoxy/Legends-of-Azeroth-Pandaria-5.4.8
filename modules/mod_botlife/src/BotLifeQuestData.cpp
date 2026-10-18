#include "BotLifeQuestData.h"

#include <algorithm>
#include <set>
#include <string>

#include "Creature.h"
#include "DatabaseEnv.h"
#include "DBCStores.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"

namespace BotLife
{
namespace
{
bool Supported(Quest const& quest)
{
    // Stage 4 deliberately excludes event, timed, repeatable, scripted and item-use quests.
    uint32 const unsupportedFlags = QUEST_FLAGS_COMPLETION_AREA_TRIGGER | QUEST_FLAGS_TRACKING_EVENT |
        QUEST_FLAGS_DAILY | QUEST_FLAGS_WEEKLY | QUEST_FLAGS_AUTO_COMPLETE | QUEST_FLAGS_AUTO_ACCEPT |
        QUEST_FLAGS_AUTO_SUBMIT | QUEST_FLAGS_AUTO_TAKE | QUEST_FLAGS_FLAGS_PVP;
    if (quest.IsUnavailable() || quest.IsTurnIn() || quest.IsSeasonal() || quest.GetSpecialFlags() ||
        (quest.GetFlags() & unsupportedFlags) || quest.GetFlagsEx() || quest.GetLimitTime() ||
        quest.GetSrcItemId() || quest.GetSrcSpell() || quest.GetScriptId() ||
        quest.GetSuggestedPlayers() > 1 || quest.GetQuestInfoID() != 0 || // No special QuestInfo category.
        quest.GetObjectives().empty() || quest.GetObjectives().size() > QUEST_OBJECTIVES_COUNT)
        return false;
    std::set<uint32> ids;
    std::set<int8> slots;
    for (QuestObjective const& objective : quest.GetObjectives())
        if (objective.Type != QUEST_OBJECTIVE_MONSTER || !objective.ID || !objective.ObjectID ||
            objective.Amount <= 0 || objective.Flags || objective.StorageIndex < 0 ||
            objective.StorageIndex >= QUEST_OBJECTIVES_COUNT || !ids.insert(objective.ID).second ||
            !slots.insert(objective.StorageIndex).second)
            return false;
    return true;
}
}

QuestPlanData LoadQuestPlanData(uint32_t questId)
{
    QuestPlanData data;
    data.questId = questId;
    Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
    if (!quest)
        return data;
    data.title = quest->GetLogTitle();
    data.error = QuestPlanReason::UnsupportedQuest;
    if (!Supported(*quest))
        return data;
    for (QuestObjective const& objective : quest->GetObjectives())
        data.objectives.push_back({objective.ID, objective.ObjectID, uint32(objective.Amount), {}});

    std::set<uint32> starters, enders, entries;
    for (auto const& relation : *sObjectMgr->GetCreatureQuestRelationMapHACK())
        if (relation.second == questId)
            starters.insert(relation.first);
    for (auto const& relation : sObjectMgr->GetCreatureQuestInvolvedRelationReverseBounds(questId))
        enders.insert(relation.second);
    entries.insert(starters.begin(), starters.end());
    entries.insert(enders.begin(), enders.end());
    // Native KillCredit aliases matter: the credit entry need not itself have a spawn.
    std::unordered_map<uint32, std::set<uint32>> sources;
    for (auto const& [entry, creature] : *sObjectMgr->GetCreatureTemplates())
        for (QuestKillObjective const& objective : data.objectives)
            if (entry == objective.entry || std::find(std::begin(creature.KillCredit),
                std::end(creature.KillCredit), objective.entry) != std::end(creature.KillCredit))
            {
                sources[objective.id].insert(entry);
                entries.insert(entry);
            }
    // Bound startup work; never silently publish a truncated plan.
    if (entries.size() > 256)
    {
        data.error = QuestPlanReason::DataLimit;
        return data;
    }
    data.error = QuestPlanReason::None;
    if (entries.empty())
        return data;
    std::string ids;
    for (uint32 entry : entries)
        ids += (ids.empty() ? "" : ",") + std::to_string(entry);
    // One bounded startup query; geometry is read from validated ObjectMgr data.
    // Dynamic events/pools and phaseID/groups need a future live resolver.
    QueryResult result = WorldDatabase.PQuery(
        "SELECT c.guid FROM creature c WHERE c.id IN ({}) "
        "AND NOT EXISTS (SELECT 1 FROM game_event_creature e WHERE e.guid=c.guid) "
        "AND NOT EXISTS (SELECT 1 FROM pool_creature p WHERE p.guid=c.guid) LIMIT 4097", ids);
    if (!result)
        return data;
    if (result->GetRowCount() > 4096)
    {
        data.error = QuestPlanReason::DataLimit;
        return data;
    }
    do
    {
        uint32 const guid = result->Fetch()[0].GetUInt32();
        CreatureData const* spawn = sObjectMgr->GetCreatureData(guid);
        if (!spawn || spawn->phaseid || spawn->phaseGroup || !spawn->phaseMask || !(spawn->spawnMask & 1))
            continue;
        MapEntry const* map = sMapStore.LookupEntry(spawn->mapId);
        if (!map || map->Instanceable() || !Trinity::IsValidMapCoord(spawn->posX, spawn->posY, spawn->posZ))
            continue;
        QuestSpawn const candidate{guid, spawn->id, spawn->mapId, spawn->phaseMask,
            spawn->posX, spawn->posY, spawn->posZ};
        if (starters.count(spawn->id))
            data.starters.push_back(candidate);
        if (enders.count(spawn->id))
            data.enders.push_back(candidate);
        for (QuestKillObjective& objective : data.objectives)
            if (sources[objective.id].count(spawn->id))
                objective.candidates.push_back(candidate);
    } while (result->NextRow());
    return data;
}

QuestPlayerSnapshot ReadQuestPlayer(QuestPlanData const& data, Player& player)
{
    QuestPlayerSnapshot snapshot;
    snapshot.validContext = player.IsInWorld() && player.IsAlive() && !player.IsBeingTeleported() &&
        player.GetMap() && !player.GetMap()->Instanceable() && !player.InBattleground() &&
        !player.IsInFlight() && !player.GetTransport() && !player.GetVehicle();
    snapshot.mapId = player.GetMapId();
    snapshot.phaseMask = player.GetPhaseMask();
    snapshot.x = player.GetPositionX();
    snapshot.y = player.GetPositionY();
    snapshot.z = player.GetPositionZ();
    if (!snapshot.validContext || data.error != QuestPlanReason::None)
        return snapshot;
    Quest const* quest = sObjectMgr->GetQuestTemplate(data.questId);
    // No retained core pointers, and fail closed if objectives were reloaded.
    if (!quest || !Supported(*quest) || quest->GetObjectives().size() != data.objectives.size())
    {
        snapshot.eligibility = QuestPlanReason::CatalogChanged;
        return snapshot;
    }
    for (size_t i = 0; i < data.objectives.size(); ++i)
    {
        QuestObjective const& objective = quest->GetObjectives()[i];
        QuestKillObjective const& cached = data.objectives[i];
        if (objective.ID != cached.id || objective.ObjectID != cached.entry || uint32(objective.Amount) != cached.amount)
        {
            snapshot.eligibility = QuestPlanReason::CatalogChanged;
            return snapshot;
        }
        snapshot.counters[objective.ID] = player.GetQuestObjectiveCounter(objective.ID);
    }
    switch (player.GetQuestStatus(data.questId))
    {
        case QUEST_STATUS_INCOMPLETE: snapshot.progress = QuestProgress::Active; break;
        case QUEST_STATUS_COMPLETE: snapshot.progress = QuestProgress::Complete; break;
        case QUEST_STATUS_FAILED: snapshot.progress = QuestProgress::Failed; break;
        case QUEST_STATUS_REWARDED: snapshot.progress = QuestProgress::Rewarded; break;
        default: snapshot.progress = QuestProgress::NotTaken; break;
    }
    if (snapshot.progress != QuestProgress::NotTaken)
        return snapshot;
    if (!Quest::IsTakingQuestEnabled(data.questId))
        snapshot.eligibility = QuestPlanReason::QuestDisabled;
    else if (!player.SatisfyQuestLevel(quest, false))
        snapshot.eligibility = QuestPlanReason::Level;
    else if (!player.SatisfyQuestRace(quest, false) || !player.SatisfyQuestClass(quest, false))
        snapshot.eligibility = QuestPlanReason::RaceOrClass;
    else if (!player.SatisfyQuestDependentQuests(quest, false))
        snapshot.eligibility = QuestPlanReason::Prerequisites;
    else if (!player.CanTakeQuest(quest, false))
        snapshot.eligibility = QuestPlanReason::NativeEligibility;
    // CanAddQuest(false) can still send inventory errors; no source item is supported here.
    else if (!player.SatisfyQuestLog(false))
        snapshot.eligibility = QuestPlanReason::QuestLogFull;
    return snapshot;
}
}
