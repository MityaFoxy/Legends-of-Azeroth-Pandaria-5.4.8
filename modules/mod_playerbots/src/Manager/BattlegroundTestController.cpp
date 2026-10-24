#include "BattlegroundTestController.h"

// Legacy battleground headers require Player's core declarations first.
#include "Player.h"
#include "BattlegroundAB.h"
#include "BattlegroundMgr.h"
#include "BotFactory.h"
#include "Creature.h"
#include "Log.h"
#include "Map.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "Playerbots.h"
#include "RandomPlayerbotMgr.h"
#include "StartingArea.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <cmath>
#include <map>
#include <set>
#include <string>

namespace
{
    constexpr uint32 MAX_QUEUE_READINESS_REPAIRS_PER_UPDATE = 2;
    constexpr uint32 QUEUE_READINESS_RETRY_INTERVAL = 60000;

    enum class QueueReadinessIssue : uint8
    {
        None,
        PendingRandomization,
        MissingEquipment,
        RepairBudget,
        RepairFailed
    };

    struct State
    {
        uint32 instance = 0;
        uint32 matches = 0;
        uint32 completed = 0;
        uint32 resurrectionInstance = 0;
        bool observedDead = false;
        uint32 lastLog = 0;
        uint32 lastRequest = 0;
        uint32 lastReadinessLog = 0;
        uint32 lastReadinessRepair = 0;
        QueueReadinessIssue readinessIssue = QueueReadinessIssue::None;
        bool requested = false;
        bool logged = false;
        bool finished = false;
        bool readinessRepairAttempted = false;
        bool initialQueueDelayStarted = false;
        std::string phase;
    };

    std::map<ObjectGuid, State> states;

    char const* QueueReadinessReason(QueueReadinessIssue issue)
    {
        switch (issue)
        {
            case QueueReadinessIssue::PendingRandomization:
                return "pending-randomization";
            case QueueReadinessIssue::MissingEquipment:
                return "missing-equipment";
            case QueueReadinessIssue::RepairBudget:
                return "repair-budget";
            case QueueReadinessIssue::RepairFailed:
                return "repair-failed";
            default:
                return "ready";
        }
    }

    bool Eligible(PlayerbotAI* ai)
    {
        return sPlayerbotAIConfig->battlegroundTest && ai && ai->GetBot() && ai->GetBot()->GetSession()
            && !ai->IsRealPlayer() && !ai->HasRealPlayerMaster()
            && sPlayerbotAIConfig->IsInRandomAccountList(ai->GetBot()->GetSession()->GetAccountId());
    }

    bool HasActiveBattlegroundMap(Player* bot, Battleground* bg)
    {
        if (!bot || !bg || !bot->IsInWorld() || bot->IsBeingTeleported())
            return false;
        Map* bgMap = bg->FindBgMap();
        return bgMap && bot->GetMap() == bgMap && bot->GetInstanceId() == bg->GetInstanceID();
    }

    uint32 EquippedCombatItems(Player* bot)
    {
        uint32 equipped = 0;
        for (uint8 slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
        {
            if (slot == EQUIPMENT_SLOT_BODY || slot == EQUIPMENT_SLOT_TABARD)
                continue;
            if (bot->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
                ++equipped;
        }
        return equipped;
    }

    void LogQueueReadiness(Player* bot, State& state, QueueReadinessIssue issue, uint32 now,
        uint32 equipped, uint32 targetLevel, char const* action)
    {
        if (state.readinessIssue == issue && getMSTimeDiff(state.lastReadinessLog, now) < 30000)
            return;
        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} queue_action={} reason={} current_level={} target_level={} equipped_items={}",
            bot->GetName(), bot->GetGUID().GetCounter(), action, QueueReadinessReason(issue),
            bot->GetLevel(), targetLevel, equipped);
        state.readinessIssue = issue;
        state.lastReadinessLog = now;
    }

    bool RepairQueueReadiness(Player* bot, State& state, uint32 now, uint32& repairBudget)
    {
        uint32 targetLevel = sRandomPlayerbotMgr->GetValue(bot, "level");
        uint32 equipped = EquippedCombatItems(bot);
        QueueReadinessIssue issue = QueueReadinessIssue::None;
        if (sRandomPlayerbotMgr->HasPendingRandomization(bot))
            issue = QueueReadinessIssue::PendingRandomization;
        else if (!equipped)
            issue = QueueReadinessIssue::MissingEquipment;
        else
        {
            state.readinessIssue = QueueReadinessIssue::None;
            state.readinessRepairAttempted = false;
            return true;
        }

        if (bot->GetInstanceId() || bot->IsInFlight())
        {
            LogQueueReadiness(bot, state, issue, now, equipped, targetLevel, "deferred");
            return false;
        }
        if (state.readinessRepairAttempted
            && getMSTimeDiff(state.lastReadinessRepair, now) < QUEUE_READINESS_RETRY_INTERVAL)
        {
            LogQueueReadiness(bot, state, issue, now, equipped, targetLevel, "repair-cooldown");
            return false;
        }
        if (!repairBudget)
        {
            LogQueueReadiness(bot, state, QueueReadinessIssue::RepairBudget, now,
                equipped, targetLevel, "deferred");
            return false;
        }

        --repairBudget;
        state.lastReadinessRepair = now;
        state.readinessRepairAttempted = true;
        if (issue == QueueReadinessIssue::PendingRandomization)
        {
            sRandomPlayerbotMgr->Randomize(bot);
            equipped = EquippedCombatItems(bot);
            bool repaired = bot->GetLevel() == targetLevel && equipped;
            LogQueueReadiness(bot, state, repaired ? issue : QueueReadinessIssue::RepairFailed,
                now, equipped, targetLevel, repaired ? "repaired" : "repair-failed");
            if (repaired)
                state.readinessRepairAttempted = false;
            return false;
        }

        BotFactory factory(bot, bot->GetLevel());
        factory.InitEquipment(false);
        equipped = EquippedCombatItems(bot);
        if (equipped)
        {
            bot->SaveToDB(false);
            LogQueueReadiness(bot, state, issue, now, equipped, targetLevel, "repaired");
            state.readinessRepairAttempted = false;
        }
        else
            LogQueueReadiness(bot, state, QueueReadinessIssue::RepairFailed,
                now, equipped, targetLevel, "repair-failed");
        return false;
    }

    bool RequestReady(State const& state, uint32 now, uint32 interval)
    {
        return !state.requested || getMSTimeDiff(state.lastRequest, now) >= interval;
    }

    void MarkRequest(State& state, uint32 now)
    {
        state.lastRequest = now;
        state.requested = true;
    }

    void LogState(Player* bot, State& state, char const* phase, uint32 now)
    {
        if (state.logged && state.phase == phase && getMSTimeDiff(state.lastLog, now) < 60000)
            return;

        Battleground* bg = bot->GetBattleground();
        BattlegroundScore const* score = nullptr;
        if (bg)
            for (auto itr = bg->GetPlayerScoresBegin(); itr != bg->GetPlayerScoresEnd(); ++itr)
                if (itr->first == bot->GetGUID())
                {
                    score = itr->second;
                    break;
                }

        float groundZ = bot->GetMapHeight(bot->GetPositionX(), bot->GetPositionY(),
            bot->GetPositionZ() + 4.0f);
        bool groundValid = std::isfinite(groundZ) && groundZ > INVALID_HEIGHT;
        float groundDelta = groundValid ? bot->GetPositionZ() - groundZ : 0.0f;
        PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
        Unit* target = nullptr;
        if (ai)
            if (Value<Unit*>* value = ai->GetAiObjectContext()->GetValue<Unit*>("current target"))
                target = value->Get();
        bool targetInMap = target && bot->IsInMap(target);

        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} phase={} level={} faction={} map={} instance={} bg_status={} bg_team={} queue={} alive={} ghost={} waiting_resurrect={} combat={} casting={} controlled={} moving={} ground_delta={} ground_valid={} hp_pct={} x={} y={} z={} ai_state={} target_guid={} target_alive={} target_distance={} target_los={} score_a={} score_h={} damage_done={} healing_done={} killing_blows={} deaths={} bases_assaulted={} bases_defended={} matches={} completed={}",
            bot->GetName(), bot->GetGUID().GetCounter(), phase, bot->GetLevel(), bot->GetTeam(),
            bot->GetMapId(), bg ? bg->GetInstanceID() : 0, bg ? uint32(bg->GetStatus()) : 0,
            bg ? bot->GetBGTeam() : bot->GetTeam(), bot->InBattlegroundQueue(), bot->IsAlive(),
            bot->HasPlayerFlag(PLAYER_FLAGS_GHOST), bot->HasAura(SPELL_WAITING_FOR_RESURRECT),
            bot->IsInCombat(), bot->HasUnitState(UNIT_STATE_CASTING),
            bot->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_FLEEING | UNIT_STATE_CONFUSED),
            bot->isMoving(), groundDelta, groundValid, bot->GetHealthPct(), bot->GetPositionX(),
            bot->GetPositionY(), bot->GetPositionZ(), ai ? int(ai->GetState()) : -1,
            target ? target->GetGUID().GetCounter() : 0, target && target->IsAlive(),
            targetInMap ? bot->GetDistance(target) : -1.0f, targetInMap && bot->IsWithinLOSInMap(target),
            bg ? bg->GetTeamScore(TEAM_ALLIANCE) : 0, bg ? bg->GetTeamScore(TEAM_HORDE) : 0,
            score ? score->DamageDone : 0, score ? score->HealingDone : 0,
            score ? score->KillingBlows : 0, score ? score->Deaths : 0,
            bg && bg->GetMapId() == 529 && score ? static_cast<BattlegroundABScore const*>(score)->BasesAssaulted : 0,
            bg && bg->GetMapId() == 529 && score ? static_cast<BattlegroundABScore const*>(score)->BasesDefended : 0,
            state.matches, state.completed);
        state.phase = phase;
        state.lastLog = now;
        state.logged = true;
    }

    void LogResurrection(Player* bot, State& state, uint32 now)
    {
        Battleground* bg = bot->GetBattleground();
        // Only an observed death -> alive transition inside the same active AB
        // counts. Leaving, preparation and transfers must not manufacture a wave.
        if (!bg || bg->GetTypeID() != BATTLEGROUND_AB || bg->IsRated()
            || !HasActiveBattlegroundMap(bot, bg) || bg->GetStatus() != STATUS_IN_PROGRESS)
        {
            state.resurrectionInstance = 0;
            state.observedDead = false;
            return;
        }

        bool alive = bot->IsAlive();
        bool resurrected = state.resurrectionInstance == bg->GetInstanceID()
            && state.observedDead && alive;
        state.resurrectionInstance = bg->GetInstanceID();
        state.observedDead = !alive;
        if (resurrected)
            LogState(bot, state, "resurrected", now);
    }

    void Join(Player* bot)
    {
        WorldPacket packet(CMSG_BATTLEMASTER_JOIN);
        packet << uint32(0) << uint32(0);
        ObjectGuid guid{uint64(BATTLEGROUND_AB)};
        for (uint8 index : {1, 7, 0, 3})
            packet.WriteBit(guid[index]);
        packet.WriteBit(false);
        packet.WriteBit(guid[4]);
        packet.WriteBit(true);
        for (uint8 index : {6, 2, 5})
            packet.WriteBit(guid[index]);
        packet.FlushBits();
        for (uint8 index : {7, 2, 4, 5, 0, 6, 3, 1})
            packet.WriteByteSeq(guid[index]);
        bot->GetSession()->HandleBattlemasterJoinOpcode(packet);
    }

    void Accept(Player* bot, uint32 slot)
    {
        WorldPacket packet(CMSG_BATTLEFIELD_PORT);
        packet << uint8(1) << slot << uint32(0) << uint32(0);
        packet << uint8(0);
        bot->GetSession()->HandleBattleFieldPortOpcode(packet);
    }

    Creature* FindSpiritGuide(Player* bot, float range)
    {
        uint32 entry = bot->GetBGTeam() == ALLIANCE
            ? BG_CREATURE_ENTRY_A_SPIRITGUIDE : BG_CREATURE_ENTRY_H_SPIRITGUIDE;
        Creature* guide = bot->FindNearestCreature(entry, range, true);
        if (!guide)
            guide = bot->FindNearestCreature(entry, range, false);
        return guide && guide->IsSpiritService() ? guide : nullptr;
    }

    void Resurrect(Player* bot)
    {
        if (!bot->HasPlayerFlag(PLAYER_FLAGS_GHOST))
        {
            WorldPacket packet(CMSG_REPOP_REQUEST);
            packet << uint8(0);
            bot->GetSession()->HandleRepopRequestOpcode(packet);
            return;
        }
        if (bot->HasAura(SPELL_WAITING_FOR_RESURRECT))
            return;
        if (Creature* guide = FindSpiritGuide(bot, INTERACTION_DISTANCE))
        {
            if (!bot->IsWithinDistInMap(guide, INTERACTION_DISTANCE))
                return;
            ObjectGuid guid = guide->GetGUID();
            WorldPacket packet(CMSG_AREA_SPIRIT_HEALER_QUEUE);
            for (uint8 index : {5, 4, 0, 2, 7, 1, 6, 3})
                packet.WriteBit(guid[index]);
            packet.FlushBits();
            for (uint8 index : {1, 7, 6, 2, 4, 3, 0, 5})
                packet.WriteByteSeq(guid[index]);
            bot->GetSession()->HandleAreaSpiritHealerQueueOpcode(packet);
        }
    }
}

void BattlegroundTest::Update(uint32 diff)
{
    if (!sPlayerbotAIConfig->battlegroundTest)
        return;

    static uint32 elapsed = 0;
    elapsed += diff;
    if (elapsed < 1000)
        return;
    elapsed = 0;

    uint32 now = getMSTime();
    uint32 repairBudget = MAX_QUEUE_READINESS_REPAIRS_PER_UPDATE;
    std::set<ObjectGuid> online;
    for (auto itr = sRandomPlayerbotMgr->GetPlayerBotsBegin(); itr != sRandomPlayerbotMgr->GetPlayerBotsEnd(); ++itr)
    {
        Player* bot = itr->second;
        PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
        if (!Eligible(ai))
            continue;

        online.insert(bot->GetGUID());
        State& state = states[bot->GetGUID()];
        LogResurrection(bot, state, now);
        if (!bot->IsInWorld() || bot->IsBeingTeleported())
        {
            LogState(bot, state, "transferring", now);
            continue;
        }
        if (Battleground* bg = bot->GetBattleground())
        {
            if (bg->GetTypeID() != BATTLEGROUND_AB || bg->IsRated())
            {
                LogState(bot, state, "foreign-bg", now);
                continue;
            }
            if (!HasActiveBattlegroundMap(bot, bg))
            {
                LogState(bot, state, "bg-map-unavailable", now);
                continue;
            }
            if (state.instance != bg->GetInstanceID())
            {
                state.instance = bg->GetInstanceID();
                ++state.matches;
                state.finished = false;
                LogState(bot, state, "entered", now);
            }
            if (bg->GetStatus() == STATUS_WAIT_LEAVE)
            {
                if (!state.finished)
                {
                    ++state.completed;
                    state.finished = true;
                }
                LogState(bot, state, "completed", now);
                if (RequestReady(state, now, 5000))
                {
                    WorldPacket packet(CMSG_BATTLEFIELD_LEAVE);
                    bot->GetSession()->HandleBattlefieldLeaveOpcode(packet);
                    MarkRequest(state, now);
                }
                continue;
            }

            char const* phase = bg->GetStatus() != STATUS_IN_PROGRESS ? "preparation"
                : !bot->IsAlive() ? "dead" : bot->IsInCombat() ? "combat" : "objective";
            LogState(bot, state, phase, now);
            if (bg->GetStatus() == STATUS_IN_PROGRESS && !bot->IsAlive()
                && RequestReady(state, now, 2000))
            {
                Resurrect(bot);
                MarkRequest(state, now);
            }
            continue;
        }

        state.instance = 0;
        BattlegroundQueueTypeId queue = BattlegroundMgr::BGQueueTypeId(BATTLEGROUND_AB, 0);
        if (bot->InBattlegroundQueue())
        {
            if (bot->IsInvitedForBattlegroundQueueType(queue) && RequestReady(state, now, 5000))
            {
                LogState(bot, state, "invited", now);
                Accept(bot, bot->GetBattlegroundQueueIndex(queue));
                MarkRequest(state, now);
            }
            else
                LogState(bot, state, "queued", now);
            continue;
        }
        if (!CanPlayerLeaveStartingArea(bot))
        {
            LogState(bot, state, "starting-area-locked", now);
            continue;
        }

        LogState(bot, state, state.finished ? "rejoin" : "online", now);
        if (!state.initialQueueDelayStarted)
        {
            state.initialQueueDelayStarted = true;
            MarkRequest(state, now);
            continue;
        }
        if (bot->IsAlive() && !bot->IsInCombat() && !bot->GetGroup()
            && RequestReady(state, now, 60000))
        {
            if (!RepairQueueReadiness(bot, state, now, repairBudget))
                continue;
            if (!bot->GetBGAccessByLevel(BATTLEGROUND_AB))
                continue;
            Join(bot);
            MarkRequest(state, now);
            if (!bot->InBattlegroundQueue())
                LogState(bot, state, "queue-rejected", now);
        }
    }

    for (auto itr = states.begin(); itr != states.end();)
        if (!online.contains(itr->first))
            itr = states.erase(itr);
        else
            ++itr;
}
