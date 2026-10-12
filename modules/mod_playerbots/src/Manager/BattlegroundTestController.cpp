#include "BattlegroundTestController.h"

// Legacy BG headers require Player's core declarations before inclusion.
#include "Player.h"
#include "BattlegroundAB.h"
#include "BattlegroundMgr.h"
#include "BotFactory.h"
#include "ChooseTargetActions.h"
#include "Creature.h"
#include "Event.h"
#include "GameObject.h"
#include "GameTime.h"
#include "Log.h"
#include "Map.h"
#include "MovementActions.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "Playerbots.h"
#include "RandomPlayerbotMgr.h"
#include "Spell.h"
#include "SpellMgr.h"
#include "StartingArea.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <algorithm>
#include <cmath>
#include <limits>
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
        uint32 team = 0;
        uint32 matches = 0;
        uint32 completed = 0;
        uint32 lastLog = 0;
        uint32 lastRequest = 0;
        bool requested = false;
        bool logged = false;
        bool finished = false;
        bool bannerLogged = false;
        uint32 lastBannerLog = 0;
        uint32 lastObjectiveReview = 0;
        uint32 approachStarted = 0;
        uint32 approachBanner = 0;
        uint8 objective = 0;
        uint8 approachVariant = 0;
        uint8 approachFailures = 0;
        uint8 preparationSlot = std::numeric_limits<uint8>::max();
        uint32 preparationInstance = 0;
        QueueReadinessIssue readinessIssue = QueueReadinessIssue::None;
        uint32 lastReadinessLog = 0;
        uint32 lastReadinessRepair = 0;
        bool readinessRepairAttempted = false;
        bool initialQueueDelayStarted = false;
        bool objectiveSet = false;
        bool approachSet = false;
        bool preparationSet = false;
        float approachX = 0.0f;
        float approachY = 0.0f;
        float approachZ = 0.0f;
        float preparationX = 0.0f;
        float preparationY = 0.0f;
        float preparationZ = 0.0f;
        std::string bannerPhase;
        std::string phase;
    };

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

        char const* phase = QueueReadinessReason(issue); // Used by the standalone regression log double.
        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} queue_action={} reason={} current_level={} target_level={} equipped_items={}",
            bot->GetName(), bot->GetGUID().GetCounter(), action, phase, bot->GetLevel(), targetLevel, equipped);
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
        // Randomize() normally equips bots, but restored or externally edited
        // character data can be naked while its long-lived randomize event still
        // says no refresh is due. Inspect the actual equipment before queueing.
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
        {
            LogQueueReadiness(bot, state, QueueReadinessIssue::RepairFailed, now,
                equipped, targetLevel, "repair-failed");
        }
        return false;
    }

    struct BannerInfo
    {
        GameObject* object = nullptr;
        uint32 type = BG_AB_OBJECT_BANNER_NEUTRAL;
    };

    // Accessed only by Update(), before map updates in World::Update.
    std::map<ObjectGuid, State> states;

    bool Eligible(PlayerbotAI* ai)
    {
        return sPlayerbotAIConfig->battlegroundTest && ai && !ai->IsRealPlayer()
            && !ai->HasRealPlayerMaster()
            && sPlayerbotAIConfig->IsInRandomAccountList(ai->GetBot()->GetSession()->GetAccountId());
    }

    bool HasActiveBattlegroundMap(Player* bot, Battleground* bg)
    {
        if (!bot || !bg || !bot->IsInWorld() || bot->IsBeingTeleported())
            return false;

        Map* bgMap = bg->FindBgMap();
        return bgMap && bot->GetMap() == bgMap && bot->GetInstanceId() == bg->GetInstanceID();
    }

    uint32 Mix(uint32 value)
    {
        value ^= value >> 16;
        value *= 0x7feb352dU;
        value ^= value >> 15;
        value *= 0x846ca68bU;
        return value ^ (value >> 16);
    }

    BannerInfo FindBanner(Battleground* bg, uint32 node)
    {
        // Battleground remains discoverable through BattlegroundMgr briefly
        // after BattlegroundMap unlinks it during teardown. GetBGObject asserts
        // when that map is gone, so never perform an object lookup in this
        // lifecycle window.
        if (!bg || !bg->FindBgMap())
            return {};
        for (uint32 type = BG_AB_OBJECT_BANNER_NEUTRAL; type <= BG_AB_OBJECT_BANNER_HORDE; ++type)
            if (GameObject* banner = bg->GetBGObject(node * 8 + type))
                if (banner->isSpawned())
                    return {banner, type};
        return {};
    }

    bool IsFriendlyBanner(Player* bot, uint32 type)
    {
        return type == (bot->GetBGTeam() == ALLIANCE ? BG_AB_OBJECT_BANNER_CONT_A : BG_AB_OBJECT_BANNER_CONT_H)
            || type == (bot->GetBGTeam() == ALLIANCE ? BG_AB_OBJECT_BANNER_ALLY : BG_AB_OBJECT_BANNER_HORDE);
    }

    char const* ObjectiveReason(Player* bot, BannerInfo const& banner)
    {
        if (!banner.object)
            return "missing-banner";
        if (banner.type == BG_AB_OBJECT_BANNER_NEUTRAL)
            return "capture-neutral";
        if (!IsFriendlyBanner(bot, banner.type))
            return banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE
                ? "assault-enemy" : "defend-contested";
        return banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE
            ? "hold-friendly" : "protect-capture";
    }

    uint32 AssignedCount(Player* bot, uint32 instance, uint32 node)
    {
        return std::count_if(states.begin(), states.end(), [bot, instance, node](auto const& entry)
        {
            State const& state = entry.second;
            return !(entry.first == bot->GetGUID()) && state.objectiveSet && state.instance == instance && state.team == bot->GetBGTeam()
                && state.objective == node;
        });
    }

    void ResetApproach(State& state)
    {
        state.approachStarted = 0;
        state.approachBanner = 0;
        state.approachVariant = 0;
        state.approachFailures = 0;
        state.approachSet = false;
    }

    bool ApproachReserved(Player* bot, State const& state, float x, float y)
    {
        for (auto const& entry : states)
        {
            State const& other = entry.second;
            if (entry.first == bot->GetGUID() || !other.approachSet || other.instance != state.instance
                || other.team != state.team || other.objective != state.objective)
                continue;

            float dx = other.approachX - x;
            float dy = other.approachY - y;
            if (dx * dx + dy * dy < 6.25f)
                return true;
        }
        return false;
    }

    bool SelectPreparationPosition(Player* bot, Battleground* bg, State& state)
    {
        constexpr uint8 PreparationSlots = 15;
        uint32 const instance = bg->GetInstanceID();
        if (state.preparationInstance != instance)
        {
            state.preparationInstance = instance;
            state.preparationSlot = std::numeric_limits<uint8>::max();
            state.preparationSet = false;
        }
        if (!state.preparationSet)
        {
            bool used[PreparationSlots] = {};
            for (auto const& entry : states)
            {
                State const& other = entry.second;
                if (entry.first != bot->GetGUID() && other.preparationSet
                    && other.preparationInstance == instance
                    && other.team == state.team && other.preparationSlot < PreparationSlots)
                    used[other.preparationSlot] = true;
            }

            uint8 start = uint8(Mix(bot->GetGUID().GetCounter()) % PreparationSlots);
            for (uint8 offset = 0; offset < PreparationSlots; ++offset)
            {
                uint8 slot = uint8((start + offset) % PreparationSlots);
                if (!used[slot])
                {
                    state.preparationSlot = slot;
                    break;
                }
            }
            if (state.preparationSlot >= PreparationSlots)
                return false;

            float startX, startY, startZ, startO;
            bg->GetTeamStartLoc(bot->GetBGTeam(), startX, startY, startZ, startO);
            uint8 door = bot->GetBGTeam() == ALLIANCE ? 0 : 1;
            float directionX = BG_AB_DoorPositions[door][0] - startX;
            float directionY = BG_AB_DoorPositions[door][1] - startY;
            float length = std::sqrt(directionX * directionX + directionY * directionY);
            if (length < 0.1f)
                return false;
            directionX /= length;
            directionY /= length;

            uint8 row = state.preparationSlot / 5;
            int8 column = int8(state.preparationSlot % 5) - 2;
            float forward = 5.0f + float(row) * 5.0f;
            float lateral = float(column) * 3.0f;
            float x = startX + directionX * forward - directionY * lateral;
            float y = startY + directionY * forward + directionX * lateral;
            // Starting rooms contain roofs and other nearby vertical layers.
            // Search only around the known native start elevation so a roof is
            // never selected as the staging destination.
            float z = bot->GetMapHeight(x, y, startZ + 1.0f, true, 3.0f);
            if (z == INVALID_HEIGHT || !Trinity::IsValidMapCoord(x, y, z))
                return false;

            state.preparationX = x;
            state.preparationY = y;
            state.preparationZ = z;
            state.preparationSet = true;
            char const* phase = "preparation-stage"; // Also labels the standalone regression log double.
            TC_LOG_INFO("playerbots.bgtest",
                "Bot={} GUID={} preparation_action=stage slot={} instance={} team={} target=({},{},{})",
                bot->GetName(), bot->GetGUID().GetCounter(), state.preparationSlot, instance,
                state.team, x, y, z);
        }
        return true;
    }

    uint32 Objective(Player* bot, Battleground* bg, State& state, uint32 now)
    {
        uint32 const reviewInterval = 20000 + Mix(bot->GetGUID().GetCounter()) % 15001;
        if (state.objectiveSet && getMSTimeDiff(state.lastObjectiveReview, now) < reviewInterval)
            return state.objective;

        uint32 previous = state.objective;
        int32 bestScore = std::numeric_limits<int32>::min();
        uint32 bestNode = previous;
        uint32 epoch = uint32(GameTime::GetGameTime() / 30);
        for (uint32 node = 0; node < BG_AB_DYNAMIC_NODES_COUNT; ++node)
        {
            BannerInfo banner = FindBanner(bg, node);
            int32 tactical = 0;
            if (!banner.object)
                tactical = 100;
            else if (banner.type == BG_AB_OBJECT_BANNER_NEUTRAL)
                tactical = 1000;
            else if (!IsFriendlyBanner(bot, banner.type))
                tactical = banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE ? 950 : 1100;
            else
                tactical = banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE ? 350 : 700;

            int32 distance = int32(std::min(bot->GetDistance2d(BG_AB_NodePositions[node][0], BG_AB_NodePositions[node][1]), 600.0f));
            int32 assigned = int32(AssignedCount(bot, bot->GetInstanceId(), node));
            int32 variation = int32(Mix(bot->GetGUID().GetCounter() ^ (epoch * 31U) ^ (node * 131U)) % 61U);
            int32 score = tactical - distance - assigned * 90 + variation;
            if (score > bestScore)
            {
                bestScore = score;
                bestNode = node;
            }
        }

        state.objective = uint8(bestNode);
        state.objectiveSet = true;
        state.lastObjectiveReview = now;
        if (bestNode != previous || !state.approachSet)
            ResetApproach(state);
        BannerInfo banner = FindBanner(bg, bestNode);
        char const* phase = "objective-selected"; // Also labels the standalone regression log double.
        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} objective_action=selected node={} previous_node={} instance={} reason={} assigned={} distance={} review_ms={}",
            bot->GetName(), bot->GetGUID().GetCounter(), bestNode, previous, bot->GetInstanceId(),
            ObjectiveReason(bot, banner), AssignedCount(bot, bot->GetInstanceId(), bestNode),
            bot->GetDistance2d(BG_AB_NodePositions[bestNode][0], BG_AB_NodePositions[bestNode][1]), reviewInterval);
        return bestNode;
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
        float groundDelta = groundZ == INVALID_HEIGHT ? 0.0f : bot->GetPositionZ() - groundZ;
        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} phase={} level={} faction={} map={} instance={} bg_status={} bg_team={} queue={} alive={} ghost={} waiting_resurrect={} combat={} moving={} flying={} can_fly={} gravity_disabled={} ground_delta={} hp_pct={} x={} y={} z={} score_a={} score_h={} damage_done={} healing_done={} killing_blows={} deaths={} matches={} completed={}",
            bot->GetName(), bot->GetGUID().GetCounter(), phase, bot->GetLevel(), bot->GetTeam(),
            bot->GetMapId(), bg ? bg->GetInstanceID() : 0, bg ? uint32(bg->GetStatus()) : 0,
            bg ? bot->GetBGTeam() : bot->GetTeam(), bot->InBattlegroundQueue(), bot->IsAlive(),
            bot->HasPlayerFlag(PLAYER_FLAGS_GHOST), bot->HasAura(SPELL_WAITING_FOR_RESURRECT),
            bot->IsInCombat(), bot->isMoving(), bot->IsFlying(), bot->CanFly(),
            bot->IsGravityDisabled(), groundDelta, bot->GetHealthPct(), bot->GetPositionX(),
            bot->GetPositionY(), bot->GetPositionZ(), bg ? bg->GetTeamScore(TEAM_ALLIANCE) : 0,
            bg ? bg->GetTeamScore(TEAM_HORDE) : 0, score ? score->DamageDone : 0,
            score ? score->HealingDone : 0, score ? score->KillingBlows : 0,
            score ? score->Deaths : 0, state.matches, state.completed);
        state.phase = phase;
        state.lastLog = now;
        state.logged = true;
    }

    void Join(Player* bot)
    {
        WorldPacket packet(CMSG_BATTLEMASTER_JOIN);
        packet << uint32(0) << uint32(0); // No blacklisted maps.
        ObjectGuid guid{uint64(BATTLEGROUND_AB)};
        for (uint8 index : {1, 7, 0, 3})
            packet.WriteBit(guid[index]);
        packet.WriteBit(false); // Individual queue, not a premade.
        packet.WriteBit(guid[4]);
        packet.WriteBit(true); // No optional role mask.
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
        packet << uint8(0); // Empty GUID bit mask; handler uses the actual queue slot.
        bot->GetSession()->HandleBattleFieldPortOpcode(packet);
    }

    Creature* FindSpiritGuide(Player* bot, float range)
    {
        uint32 entry = bot->GetBGTeam() == ALLIANCE ? BG_CREATURE_ENTRY_A_SPIRITGUIDE : BG_CREATURE_ENTRY_H_SPIRITGUIDE;
        // AddSpiritGuide starts DEAD, but Creature::Respawn can make it ALIVE.
        // The native queue handler checks SpiritService, not the death state.
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
        // Only a nearby spirit guide; the core owns the resurrection wave timer.
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
            return;
        }
    }

    bool AtBanner(Player* bot, GameObject* banner)
    {
        SpellInfo const* opening = sSpellMgr->GetSpellInfo(21651);
        // Match the real interaction boundary, then submit the same normal,
        // non-triggered GameObject-targeted spell as a player. Spell::CheckCast
        // and the battleground own the authoritative validation; imposing an
        // extra WorldObject LOS ray here rejects valid flag interactions.
        return opening && banner && banner->isSpawned() && banner->IsAtInteractDistance(bot, opening);
    }

    void LogBanner(Player* bot, State& state, uint32 now, char const* phase, GameObject* banner = nullptr)
    {
        if (state.bannerLogged && state.bannerPhase == phase
            && getMSTimeDiff(state.lastBannerLog, now) < 30000)
            return;
        TC_LOG_INFO("playerbots.bgtest",
            "Bot={} GUID={} banner_action={} node={} instance={} banner_guid={} banner_entry={} distance={} los={} native_usable={} moving={} casting={}",
            bot->GetName(), bot->GetGUID().GetCounter(), phase, state.objective,
            bot->GetInstanceId(), banner ? banner->GetGUID().GetCounter() : 0,
            banner ? banner->GetEntry() : 0, banner ? bot->GetExactDist(banner) : -1.0f,
            banner && bot->IsWithinLOSInMap(banner), banner && bot->CanUseBattlegroundObject(banner),
            bot->isMoving(), bot->HasUnitState(UNIT_STATE_CASTING));
        state.bannerLogged = true;
        state.lastBannerLog = now;
        state.bannerPhase = phase;
    }

    void UseBanner(Player* bot, Battleground* bg, State& state, uint32 now)
    {
        if (bot->IsInCombat() || bot->HasUnitState(UNIT_STATE_CASTING) || bot->IsMounted())
            return;
        if (!HasActiveBattlegroundMap(bot, bg))
        {
            LogBanner(bot, state, now, "bg-map-unavailable");
            return;
        }
        if (!sSpellMgr->GetSpellInfo(21651))
        {
            LogBanner(bot, state, now, "missing-opening-spell");
            return;
        }
        uint32 node = state.objective;
        uint32 friendlyContested = bot->GetBGTeam() == ALLIANCE ? BG_AB_OBJECT_BANNER_CONT_A : BG_AB_OBJECT_BANNER_CONT_H;
        uint32 friendlyOccupied = bot->GetBGTeam() == ALLIANCE ? BG_AB_OBJECT_BANNER_ALLY : BG_AB_OBJECT_BANNER_HORDE;
        GameObject* spawned = nullptr;
        bool friendly = false;
        for (uint32 type = BG_AB_OBJECT_BANNER_NEUTRAL; type <= BG_AB_OBJECT_BANNER_HORDE; ++type)
        {
            GameObject* banner = bg->GetBGObject(node * 8 + type);
            if (!banner || !banner->isSpawned())
                continue;
            spawned = banner;
            friendly = type == friendlyContested || type == friendlyOccupied;
            if (friendly || !AtBanner(bot, banner))
                continue;
            // The client opens AB's locked banners with Opening, NOT GAMEOBJ_USE
            // (occupied banners are buttons; Use would only toggle the button).
            // Normal, non-triggered Spell::CheckCast/EffectOpenLock own validation,
            // cast time and interrupts. Never call EventPlayerClickedOnFlag directly.
            bot->StopMoving();
            bot->CastSpell(banner, 21651, false);
            Spell* current = bot->GetCurrentSpell(CURRENT_GENERIC_SPELL);
            // Starting a cast is not proof of capture: damage/movement can
            // still interrupt it, and only the BG decides the node outcome.
            LogBanner(bot, state, now, current && current->GetSpellInfo()->Id == 21651
                ? "capture-started" : "capture-not-started", banner);
            return;
        }
        LogBanner(bot, state, now, !spawned ? "no-spawned-banner" : friendly ? "friendly-node"
            : !spawned->IsAtInteractDistance(bot, sSpellMgr->GetSpellInfo(21651)) ? "out-of-range" : "line-of-sight", spawned);
    }

    bool SelectApproach(Player* bot, State& state, GameObject* banner, bool friendly, uint32 now)
    {
        uint32 bannerGuid = banner->GetGUID().GetCounter();
        if (state.approachBanner != bannerGuid)
        {
            ResetApproach(state);
            state.approachBanner = bannerGuid;
        }

        uint32 const variants = friendly ? 24 : 32;
        uint32 const start = Mix(bot->GetGUID().GetCounter() ^ (state.objective * 131U)) % variants;
        for (uint32 offset = 0; offset < variants; ++offset)
        {
            uint32 variant = (start + state.approachVariant + offset) % variants;
            uint32 directions = friendly ? 12 : 16;
            float radius = friendly ? (variant < directions ? 6.5f : 10.0f)
                : (variant < directions ? 2.75f : 4.25f);
            float angle = float(2.0 * M_PI) * float(variant % directions) / float(directions);
            float x = banner->GetPositionX() + std::cos(angle) * radius;
            float y = banner->GetPositionY() + std::sin(angle) * radius;
            float z = bot->GetMapHeight(x, y, banner->GetPositionZ() + 6.0f);
            if (z == INVALID_HEIGHT || !Trinity::IsValidMapCoord(x, y, z))
                continue;
            if (ApproachReserved(bot, state, x, y))
                continue;
            // A speculative LOS ray from a position the player has not yet
            // reached is not a safe routing gate: dynamic flag geometry can
            // reject every point before PathGenerator receives a request.
            // After arrival UseBanner submits the native non-triggered cast.
            state.approachX = x;
            state.approachY = y;
            state.approachZ = z;
            state.approachStarted = now;
            state.approachSet = true;
            state.approachVariant = uint8((variant + 1) % variants);
            return true;
        }
        state.approachSet = false;
        return false;
    }

    class PreparationMovement : public MovementAction
    {
    public:
        PreparationMovement(PlayerbotAI* ai, Battleground* bg, State& state)
            : MovementAction(ai, "BG test preparation"), bg(bg), state(state) { }

        bool Execute(Event) override
        {
            if (!SelectPreparationPosition(bot, bg, state))
                return false;

            float dx = bot->GetPositionX() - state.preparationX;
            float dy = bot->GetPositionY() - state.preparationY;
            float dz = bot->GetPositionZ() - state.preparationZ;
            if (dx * dx + dy * dy + dz * dz <= 1.5625f)
            {
                if (bot->isMoving())
                    bot->StopMoving();
                return true;
            }
            if (bot->isMoving())
                return true;

            // The target stays well inside StartMaxDist and behind the closed
            // gate. Navigation must find a ground route; no direct fallback is
            // allowed during preparation.
            return MoveTo(bot->GetMapId(), state.preparationX, state.preparationY,
                state.preparationZ, false, false, true);
        }

    private:
        Battleground* bg;
        State& state;
    };

    class ObjectiveMovement : public MovementAction
    {
    public:
        ObjectiveMovement(PlayerbotAI* ai, Battleground* bg, State& state, uint32 now)
            : MovementAction(ai, "BG test objective"), bg(bg), state(state), now(now) { }
        bool Execute(Event) override
        {
            if (!bot->IsAlive())
            {
                if (Creature* guide = FindSpiritGuide(bot, sPlayerbotAIConfig->sightDistance))
                {
                    if (bot->IsWithinDistInMap(guide, INTERACTION_DISTANCE))
                    {
                        if (bot->isMoving())
                            bot->StopMoving();
                        return true;
                    }
                    return MoveNear(guide, INTERACTION_DISTANCE * 0.5f);
                }
                return false;
            }
            uint32 node = state.objective;
            // The objective is the native interaction area, not the exact
            // banner origin (which can be outside the walkable polygon).
            BannerInfo banner = FindBanner(bg, node);
            if (banner.object)
            {
                bool friendly = IsFriendlyBanner(bot, banner.type);
                if (!friendly && AtBanner(bot, banner.object))
                {
                    if (bot->isMoving())
                        bot->StopMoving();
                    return true;
                }
                if (friendly && bot->GetDistance2d(banner.object) <= 12.0f)
                {
                    if (bot->isMoving())
                        bot->StopMoving();
                    return true;
                }

                if (state.approachSet)
                {
                    float dx = bot->GetPositionX() - state.approachX;
                    float dy = bot->GetPositionY() - state.approachY;
                    float dz = bot->GetPositionZ() - state.approachZ;
                    if (std::sqrt(dx * dx + dy * dy + dz * dz) <= 1.25f)
                    {
                        state.approachSet = false;
                        ++state.approachFailures;
                    }
                    else if (bot->isMoving())
                        return true;
                }

                if (!state.approachSet && !SelectApproach(bot, state, banner.object, friendly, now))
                {
                    LogBanner(bot, state, now, "no-valid-approach", banner.object);
                    return false;
                }

                if (MoveTo(bot->GetMapId(), state.approachX, state.approachY, state.approachZ,
                    false, false, true))
                    return true;
                if (getMSTimeDiff(state.approachStarted, now) >= 3000)
                {
                    state.approachSet = false;
                    ++state.approachFailures;
                    LogBanner(bot, state, now, "approach-route-failed", banner.object);
                }
                return true;
            }
            return MoveTo(bot->GetMapId(), BG_AB_NodePositions[node][0], BG_AB_NodePositions[node][1],
                BG_AB_NodePositions[node][2], false, false, true);
        }

    private:
        Battleground* bg;
        State& state;
        uint32 now;
    };
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
                state.team = bot->GetBGTeam();
                state.objectiveSet = false;
                state.lastObjectiveReview = 0;
                if (state.preparationInstance != bg->GetInstanceID())
                {
                    state.preparationSlot = std::numeric_limits<uint8>::max();
                    state.preparationSet = false;
                }
                ResetApproach(state);
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
            if (state.phase == "dead" && bot->IsAlive())
                LogState(bot, state, "resurrected", now);
            if (bg->GetStatus() == STATUS_IN_PROGRESS && bot->IsAlive())
                Objective(bot, bg, state, now);
            LogState(bot, state, phase, now);
            if (bg->GetStatus() == STATUS_IN_PROGRESS && RequestReady(state, now, 2000))
            {
                if (!bot->IsAlive())
                    Resurrect(bot);
                else
                {
                    BannerInfo banner = FindBanner(bg, state.objective);
                    if (bot->IsMounted() && banner.object && !IsFriendlyBanner(bot, banner.type)
                        && bot->GetDistance2d(banner.object) <= 12.0f)
                    {
                        WorldPacket packet(CMSG_CANCEL_MOUNT_AURA);
                        bot->GetSession()->HandleCancelMountAuraOpcode(packet);
                    }
                    UseBanner(bot, bg, state, now);
                }
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
        // Give the bracket distributor one complete pass before this opt-in
        // workload occupies every native queue. Subsequent requeues retain the
        // normal per-bot request interval.
        if (!state.initialQueueDelayStarted)
        {
            state.initialQueueDelayStarted = true;
            MarkRequest(state, now);
            continue;
        }
        // Resolve an already scheduled level change and repair missing equipment
        // before joining. Faction, grouping, deserter and native eligibility rules
        // remain owned by the normal individual queue handler.
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

bool BattlegroundTest::DoNextAction(PlayerbotAI* ai)
{
    if (!Eligible(ai))
        return false;
    Player* bot = ai->GetBot();
    Battleground* bg = bot->GetBattleground();
    if (!bg || bg->GetTypeID() != BATTLEGROUND_AB || bg->IsRated())
        return false;
    if (!HasActiveBattlegroundMap(bot, bg))
    {
        ai->SetNextCheckDelay(1000);
        return true;
    }
    if (bot->isAFK())
        bot->ToggleAFK();
    State& state = states[bot->GetGUID()];
    uint32 now = getMSTime();
    state.team = bot->GetBGTeam();
    if (bg->GetStatus() != STATUS_IN_PROGRESS || !bot->IsAlive())
    {
        if (bg->GetStatus() == STATUS_WAIT_JOIN && bot->IsAlive())
            PreparationMovement(ai, bg, state).Execute(Event());
        else if (bg->GetStatus() == STATUS_IN_PROGRESS && bot->HasPlayerFlag(PLAYER_FLAGS_GHOST)
            && !bot->HasAura(SPELL_WAITING_FOR_RESURRECT))
            ObjectiveMovement(ai, bg, state, now).Execute(Event());
        ai->SetNextCheckDelay(1000);
        return true; // No ordinary corpse revival/roaming during BG preparation.
    }
    Objective(bot, bg, state, now);
    if (bot->IsInCombat() || ai->GetState() == BOT_STATE_COMBAT)
        return false; // Existing class combat/healing engine remains in charge.
    if (!bot->HasUnitState(UNIT_STATE_CASTING))
    {
        AttackEnemyPlayerAction attack(ai);
        if (attack.isUseful() && attack.Execute(Event()))
            return false;
        ObjectiveMovement(ai, bg, state, now).Execute(Event());
    }
    ai->SetNextCheckDelay(1000); // Recheck nearby enemies without waiting for a long route.
    return true;
}
