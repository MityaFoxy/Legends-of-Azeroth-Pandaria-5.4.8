#include "ArathiBasinPlayerbot.h"

// Legacy battleground headers require Player's core declarations first.
#include "Player.h"
#include "BattlegroundAB.h"
#include "BattlegroundMgr.h"
#include "ChooseTargetActions.h"
#include "DBCStores.h"
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
#include <utility>

namespace
{
    constexpr uint32 AB_MAP_ID = 529;
    constexpr uint32 OPENING_SPELL_ID = 21651;
    constexpr uint32 MAX_QUEUE_REQUESTS_PER_UPDATE = 4;

    struct BannerInfo
    {
        GameObject* object = nullptr;
        uint32 type = BG_AB_OBJECT_BANNER_NEUTRAL;
    };

    uint32 Mix(uint32 value)
    {
        value ^= value >> 16;
        value *= 0x7feb352dU;
        value ^= value >> 15;
        value *= 0x846ca68bU;
        return value ^ (value >> 16);
    }

    bool Eligible(PlayerbotAI* ai)
    {
        return ai && ai->GetBot() && ai->GetBot()->GetSession() && !ai->IsRealPlayer();
    }

    bool Autonomous(PlayerbotAI* ai)
    {
        return Eligible(ai) && !ai->HasRealPlayerMaster()
            && sPlayerbotAIConfig->IsInRandomAccountList(ai->GetBot()->GetSession()->GetAccountId());
    }

    bool HasActiveBattlegroundMap(Player* bot, Battleground* bg)
    {
        if (!bot || !bg || !bot->IsInWorld() || bot->IsBeingTeleported())
            return false;

        Map* bgMap = bg->FindBgMap();
        return bgMap && bot->GetMap() == bgMap && bot->GetInstanceId() == bg->GetInstanceID();
    }

    void ResetApproach(ArathiBasinPlayerbot::State& state)
    {
        state.approachStarted = 0;
        state.approachRouteFailureStarted = 0;
        state.approachBanner = 0;
        state.approachVariant = 0;
        state.approachFailures = 0;
        state.approachSet = false;
    }

    void ResetObjective(ArathiBasinPlayerbot::State& state)
    {
        state.objectiveInstance = 0;
        state.team = 0;
        state.lastObjectiveReview = 0;
        state.objective = 0;
        state.objectiveSet = false;
        state.wasAlive = false;
        state.bannerLogged = false;
        state.bannerPhase.clear();
        ResetApproach(state);
    }

    BannerInfo FindBanner(Battleground* bg, uint32 node)
    {
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

    Player* FindFriendlyBannerCapturer(Player* bot, GameObject* banner, bool includeSelf)
    {
        if (!banner || !bot->GetMap())
            return nullptr;

        for (auto const& reference : bot->GetMap()->GetPlayers())
        {
            Player* other = reference.GetSource();
            if (!other || (!includeSelf && other == bot) || !other->IsAlive()
                || other->GetBGTeam() != bot->GetBGTeam())
                continue;
            Spell* spell = other->GetCurrentSpell(CURRENT_GENERIC_SPELL);
            if (spell && spell->GetSpellInfo()->Id == OPENING_SPELL_ID
                && spell->m_targets.GetGOTargetGUID() == banner->GetGUID())
                return other;
        }
        return nullptr;
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

    uint32 AssignedCount(Player* bot, uint32 node)
    {
        uint32 count = 0;
        if (!bot->GetMap())
            return count;

        for (auto const& reference : bot->GetMap()->GetPlayers())
        {
            Player* other = reference.GetSource();
            PlayerbotAI* otherAI = other ? GET_PLAYERBOT_AI(other) : nullptr;
            if (!otherAI || other == bot || other->GetBGTeam() != bot->GetBGTeam())
                continue;
            ArathiBasinPlayerbot::State const& otherState = otherAI->GetArathiBasinState();
            if (otherState.objectiveSet && otherState.objectiveInstance == bot->GetInstanceId()
                && otherState.team == bot->GetBGTeam() && otherState.objective == node)
                ++count;
        }
        return count;
    }

    bool ApproachReserved(Player* bot, ArathiBasinPlayerbot::State const& state, float x, float y)
    {
        if (!bot->GetMap())
            return false;

        for (auto const& reference : bot->GetMap()->GetPlayers())
        {
            Player* other = reference.GetSource();
            PlayerbotAI* otherAI = other ? GET_PLAYERBOT_AI(other) : nullptr;
            if (!otherAI || other == bot)
                continue;
            ArathiBasinPlayerbot::State const& otherState = otherAI->GetArathiBasinState();
            if (!otherState.approachSet || otherState.objectiveInstance != state.objectiveInstance
                || otherState.team != state.team || otherState.objective != state.objective)
                continue;

            float dx = otherState.approachX - x;
            float dy = otherState.approachY - y;
            if (dx * dx + dy * dy < 6.25f)
                return true;
        }
        return false;
    }

    bool ApproachOccupied(Player* bot, float x, float y, float z)
    {
        if (!bot->GetMap())
            return false;

        for (auto const& reference : bot->GetMap()->GetPlayers())
        {
            Player* other = reference.GetSource();
            if (!other || other == bot || !other->IsAlive() || other->GetBGTeam() != bot->GetBGTeam())
                continue;
            float dx = other->GetPositionX() - x;
            float dy = other->GetPositionY() - y;
            if (dx * dx + dy * dy < 4.0f && std::fabs(other->GetPositionZ() - z) < 2.0f)
                return true;
        }
        return false;
    }

    uint32 SelectObjective(Player* bot, Battleground* bg, ArathiBasinPlayerbot::State& state, uint32 now)
    {
        if (state.objectiveSet)
        {
            BannerInfo current = FindBanner(bg, state.objective);
            // Hold the node while a friendly player is performing the real
            // Opening cast. Nearby bots remain defenders instead of racing to
            // start the same capture.
            if (current.object && FindFriendlyBannerCapturer(bot, current.object, true))
                return state.objective;
        }

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
                tactical = banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE
                    ? 950 : 1100;
            else
                tactical = banner.type == BG_AB_OBJECT_BANNER_ALLY || banner.type == BG_AB_OBJECT_BANNER_HORDE
                    ? 350 : 700;

            int32 distance = int32(std::min(bot->GetDistance2d(
                BG_AB_NodePositions[node][0], BG_AB_NodePositions[node][1]), 600.0f));
            int32 assigned = int32(AssignedCount(bot, node));
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
        if (bestNode != previous)
            ResetApproach(state);

        BannerInfo banner = FindBanner(bg, bestNode);
        TC_LOG_DEBUG("playerbots.bg",
            "Bot={} GUID={} objective_action=selected node={} previous_node={} instance={} reason={} assigned={} distance={} review_ms={}",
            bot->GetName(), bot->GetGUID().GetCounter(), bestNode, previous, bot->GetInstanceId(),
            ObjectiveReason(bot, banner), AssignedCount(bot, bestNode),
            bot->GetDistance2d(BG_AB_NodePositions[bestNode][0], BG_AB_NodePositions[bestNode][1]), reviewInterval);
        return bestNode;
    }

    bool AtBanner(Player* bot, GameObject* banner)
    {
        SpellInfo const* opening = sSpellMgr->GetSpellInfo(OPENING_SPELL_ID);
        return opening && banner && banner->isSpawned() && banner->IsAtInteractDistance(bot, opening);
    }

    void LogBanner(Player* bot, ArathiBasinPlayerbot::State& state, uint32 now,
        char const* phase, GameObject* banner = nullptr)
    {
        if (state.bannerLogged && state.bannerPhase == phase
            && getMSTimeDiff(state.lastBannerLog, now) < 30000)
            return;
        TC_LOG_DEBUG("playerbots.bg",
            "Bot={} GUID={} banner_action={} node={} instance={} banner_guid={} banner_entry={} distance={} native_usable={} moving={} casting={}",
            bot->GetName(), bot->GetGUID().GetCounter(), phase, state.objective,
            bot->GetInstanceId(), banner ? banner->GetGUID().GetCounter() : 0,
            banner ? banner->GetEntry() : 0, banner ? bot->GetExactDist(banner) : -1.0f,
            banner && bot->CanUseBattlegroundObject(banner), bot->isMoving(),
            bot->HasUnitState(UNIT_STATE_CASTING));
        state.bannerLogged = true;
        state.lastBannerLog = now;
        state.bannerPhase = phase;
    }

    void UseBanner(Player* bot, Battleground* bg, ArathiBasinPlayerbot::State& state, uint32 now)
    {
        if (bot->IsInCombat() || bot->HasUnitState(UNIT_STATE_CASTING) || bot->IsMounted())
            return;
        if (!HasActiveBattlegroundMap(bot, bg))
            return;
        if (!sSpellMgr->GetSpellInfo(OPENING_SPELL_ID))
        {
            LogBanner(bot, state, now, "missing-opening-spell");
            return;
        }

        uint32 friendlyContested = bot->GetBGTeam() == ALLIANCE
            ? BG_AB_OBJECT_BANNER_CONT_A : BG_AB_OBJECT_BANNER_CONT_H;
        uint32 friendlyOccupied = bot->GetBGTeam() == ALLIANCE
            ? BG_AB_OBJECT_BANNER_ALLY : BG_AB_OBJECT_BANNER_HORDE;
        for (uint32 type = BG_AB_OBJECT_BANNER_NEUTRAL; type <= BG_AB_OBJECT_BANNER_HORDE; ++type)
        {
            GameObject* banner = bg->GetBGObject(state.objective * 8 + type);
            if (!banner || !banner->isSpawned())
                continue;
            bool friendly = type == friendlyContested || type == friendlyOccupied;
            if (friendly || !AtBanner(bot, banner))
                continue;
            if (FindFriendlyBannerCapturer(bot, banner, false))
            {
                LogBanner(bot, state, now, "ally-capturing", banner);
                return;
            }
            if (ApproachOccupied(bot, bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ()))
                return;

            // Submit the same normal, interruptible GameObject-targeted spell
            // as a client. Spell::CheckCast and AB own the capture outcome.
            bot->StopMoving();
            bot->CastSpell(banner, OPENING_SPELL_ID, false);
            Spell* current = bot->GetCurrentSpell(CURRENT_GENERIC_SPELL);
            LogBanner(bot, state, now, current && current->GetSpellInfo()->Id == OPENING_SPELL_ID
                ? "capture-started" : "capture-not-started", banner);
            return;
        }
    }

    bool SelectApproach(Player* bot, ArathiBasinPlayerbot::State& state,
        GameObject* banner, bool friendly, uint32 now)
    {
        uint32 bannerGuid = banner->GetGUID().GetCounter();
        if (state.approachBanner != bannerGuid)
        {
            ResetApproach(state);
            state.approachBanner = bannerGuid;
        }

        uint32 const variants = friendly ? 24 : 32;
        uint32 const directions = friendly ? 12 : 16;
        uint32 const start = Mix(bot->GetGUID().GetCounter() ^ (state.objective * 131U)) % variants;
        for (uint32 offset = 0; offset < variants; ++offset)
        {
            uint32 variant = (start + state.approachVariant + offset) % variants;
            float radius = friendly ? (variant < directions ? 6.5f : 10.0f)
                : (variant < directions ? 2.75f : 4.25f);
            float angle = float(2.0 * M_PI) * float(variant % directions) / float(directions);
            float x = banner->GetPositionX() + std::cos(angle) * radius;
            float y = banner->GetPositionY() + std::sin(angle) * radius;
            float z = bot->GetMapHeight(x, y, banner->GetPositionZ());
            if (z <= INVALID_HEIGHT || !Trinity::IsValidMapCoord(x, y, z))
                continue;
            if (ApproachReserved(bot, state, x, y) || ApproachOccupied(bot, x, y, z))
                continue;

            state.approachX = x;
            state.approachY = y;
            state.approachZ = z;
            state.approachStarted = now;
            state.approachRouteFailureStarted = 0;
            state.approachSet = true;
            state.approachVariant = uint8((state.approachVariant + offset + 1) % variants);
            return true;
        }
        state.approachSet = false;
        return false;
    }

    class CombatSeparationMovement : public MovementAction
    {
    public:
        CombatSeparationMovement(PlayerbotAI* ai, ArathiBasinPlayerbot::State& state, uint32 now)
            : MovementAction(ai, "AB combat separation"), state(state), now(now) { }

        bool Execute(Event) override
        {
            if (bot->isMoving() || bot->HasUnitState(UNIT_STATE_CASTING) || !IsMovingAllowed()
                || getMSTimeDiff(state.lastSeparation, now) < 2000)
                return false;

            bool overlapping = false;
            for (auto const& reference : bot->GetMap()->GetPlayers())
            {
                Player* other = reference.GetSource();
                if (!other || !other->IsAlive() || other->isMoving()
                    || other->GetGUID().GetCounter() >= bot->GetGUID().GetCounter())
                    continue;
                float dx = bot->GetPositionX() - other->GetPositionX();
                float dy = bot->GetPositionY() - other->GetPositionY();
                if (dx * dx + dy * dy < 0.25f && std::fabs(bot->GetPositionZ() - other->GetPositionZ()) < 1.0f)
                {
                    overlapping = true;
                    break;
                }
            }
            if (!overlapping)
                return false;

            state.lastSeparation = now;
            uint32 start = Mix(bot->GetGUID().GetCounter()) % 16;
            for (uint32 attempt = 0; attempt < 8; ++attempt)
            {
                float angle = float(2.0 * M_PI) * float((start + attempt * 3) % 16) / 16.0f;
                float x = bot->GetPositionX() + std::cos(angle) * 2.5f;
                float y = bot->GetPositionY() + std::sin(angle) * 2.5f;
                float z = bot->GetMapHeight(x, y, bot->GetPositionZ() + 2.0f, true, 4.0f);
                if (z <= INVALID_HEIGHT || !Trinity::IsValidMapCoord(x, y, z)
                    || std::fabs(z - bot->GetPositionZ()) > 2.0f || ApproachOccupied(bot, x, y, z))
                    continue;
                if (MoveTo(bot->GetMapId(), x, y, z, false, false, true, false,
                    MovementPriority::MOVEMENT_COMBAT))
                    return true;
            }
            return false;
        }

    private:
        ArathiBasinPlayerbot::State& state;
        uint32 now;
    };

    class ObjectiveMovement : public MovementAction
    {
    public:
        ObjectiveMovement(PlayerbotAI* ai, Battleground* bg,
            ArathiBasinPlayerbot::State& state, uint32 now)
            : MovementAction(ai, "AB objective"), bg(bg), state(state), now(now) { }

        bool Execute(Event) override
        {
            BannerInfo banner = FindBanner(bg, state.objective);
            if (!banner.object)
                return true; // AB may briefly replace the banner during a state change.

            bool friendly = IsFriendlyBanner(bot, banner.type);
            if (state.approachBanner != banner.object->GetGUID().GetCounter())
            {
                // Preserve an in-flight node approach while AB swaps the flag
                // GameObject; only a missing approach needs a full reset.
                if (!state.approachSet)
                    ResetApproach(state);
                state.approachBanner = banner.object->GetGUID().GetCounter();
            }
            if (!friendly && AtBanner(bot, banner.object)
                && !ApproachOccupied(bot, bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ()))
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
                if (ApproachOccupied(bot, state.approachX, state.approachY, state.approachZ))
                {
                    state.approachSet = false;
                    state.approachRouteFailureStarted = 0;
                }
                else if (std::sqrt(dx * dx + dy * dy + dz * dz) <= 0.75f)
                {
                    state.approachRouteFailureStarted = 0;
                    if (friendly)
                    {
                        if (bot->isMoving())
                            bot->StopMoving();
                        return true;
                    }
                    state.approachSet = false;
                    ++state.approachFailures;
                }
                else if (bot->isMoving())
                {
                    state.approachRouteFailureStarted = 0;
                    return true;
                }
            }

            if (!state.approachSet && !SelectApproach(bot, state, banner.object, friendly, now))
            {
                if (!state.approachRouteFailureStarted)
                    state.approachRouteFailureStarted = now;
                else if (getMSTimeDiff(state.approachRouteFailureStarted, now) >= 3000)
                    LogBanner(bot, state, now, "no-valid-approach", banner.object);
                return true;
            }

            if (MoveTo(bot->GetMapId(), state.approachX, state.approachY, state.approachZ,
                false, false, true))
            {
                state.approachRouteFailureStarted = 0;
                return true;
            }
            if (lastMoveFailure == MoveFailure::None)
            {
                state.approachRouteFailureStarted = 0;
                return true;
            }
            if (!state.approachRouteFailureStarted)
                state.approachRouteFailureStarted = now;
            else if (getMSTimeDiff(state.approachRouteFailureStarted, now) >= 3000)
            {
                state.approachSet = false;
                state.approachRouteFailureStarted = 0;
                ++state.approachFailures;
                LogBanner(bot, state, now, lastMoveFailure == MoveFailure::Route
                    ? "approach-route-failed" : "approach-recovery-exhausted", banner.object);
            }
            return true;
        }

    private:
        Battleground* bg;
        ArathiBasinPlayerbot::State& state;
        uint32 now;
    };

    bool RequestReady(ArathiBasinPlayerbot::State const& state, uint32 now, uint32 interval)
    {
        return !state.queueRequested || getMSTimeDiff(state.lastQueueRequest, now) >= interval;
    }

    void MarkRequest(ArathiBasinPlayerbot::State& state, uint32 now)
    {
        state.lastQueueRequest = now;
        state.queueRequested = true;
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
}

void ArathiBasinPlayerbot::Update(uint32 diff)
{
    if (!sPlayerbotAIConfig->randomBotJoinBG || !sPlayerbotAIConfig->randomBotAutoJoinBG
        || !sPlayerbotAIConfig->randomBotAutoJoinBGABCount || sPlayerbotAIConfig->battlegroundTest)
        return;

    static uint32 elapsed = 0;
    elapsed += diff;
    if (elapsed < 1000)
        return;
    elapsed = 0;

    Battleground* bgTemplate = sBattlegroundMgr->GetBattlegroundTemplate(BATTLEGROUND_AB);
    if (!bgTemplate)
        return;

    BattlegroundQueueTypeId queue = BattlegroundMgr::BGQueueTypeId(BATTLEGROUND_AB, 0);
    uint32 targetPerTeam = bgTemplate->GetMaxPlayersPerTeam()
        * sPlayerbotAIConfig->randomBotAutoJoinBGABCount;
    std::map<std::pair<uint8, uint8>, uint32> participants;

    for (auto itr = sRandomPlayerbotMgr->GetPlayerBotsBegin(); itr != sRandomPlayerbotMgr->GetPlayerBotsEnd(); ++itr)
    {
        Player* bot = itr->second;
        PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
        if (!Autonomous(ai))
            continue;
        PvPDifficultyEntry const* bracket = sDBCManager.GetBattlegroundBracketByLevel(AB_MAP_ID, bot->GetLevel());
        if (!bracket || !sPlayerbotAIConfig->randomBotAutoJoinABBrackets.contains(bracket->GetBracketId()))
            continue;
        if ((bot->GetBattleground() && bot->GetBattleground()->GetTypeID() == BATTLEGROUND_AB)
            || bot->InBattlegroundQueueForBattlegroundQueueType(queue))
            ++participants[{uint8(bracket->GetBracketId()), uint8(bot->GetTeamId())}];
    }

    uint32 now = getMSTime();
    uint32 joinBudget = MAX_QUEUE_REQUESTS_PER_UPDATE;
    for (auto itr = sRandomPlayerbotMgr->GetPlayerBotsBegin(); itr != sRandomPlayerbotMgr->GetPlayerBotsEnd(); ++itr)
    {
        Player* bot = itr->second;
        PlayerbotAI* ai = GET_PLAYERBOT_AI(bot);
        if (!Autonomous(ai) || !bot->IsInWorld() || bot->IsBeingTeleported())
            continue;
        State& state = ai->GetArathiBasinState();

        if (Battleground* bg = bot->GetBattleground())
        {
            if (bg->GetTypeID() == BATTLEGROUND_AB && !bg->IsRated()
                && bg->GetStatus() == STATUS_WAIT_LEAVE && RequestReady(state, now, 5000))
            {
                WorldPacket packet(CMSG_BATTLEFIELD_LEAVE);
                bot->GetSession()->HandleBattlefieldLeaveOpcode(packet);
                MarkRequest(state, now);
            }
            continue;
        }
        if (bot->InBattlegroundQueue())
        {
            if (bot->IsInvitedForBattlegroundQueueType(queue) && RequestReady(state, now, 5000))
            {
                Accept(bot, bot->GetBattlegroundQueueIndex(queue));
                MarkRequest(state, now);
            }
            continue;
        }
        if (!joinBudget || !bot->IsAlive() || bot->IsInCombat() || bot->GetGroup()
            || bot->IsInFlight() || !CanPlayerLeaveStartingArea(bot) || !bot->GetBGAccessByLevel(BATTLEGROUND_AB)
            || !RequestReady(state, now, 60000))
            continue;

        PvPDifficultyEntry const* bracket = sDBCManager.GetBattlegroundBracketByLevel(AB_MAP_ID, bot->GetLevel());
        if (!bracket || !sPlayerbotAIConfig->randomBotAutoJoinABBrackets.contains(bracket->GetBracketId()))
            continue;
        auto key = std::make_pair(uint8(bracket->GetBracketId()), uint8(bot->GetTeamId()));
        if (participants[key] >= targetPerTeam)
            continue;

        Join(bot);
        MarkRequest(state, now);
        --joinBudget;
        if (bot->InBattlegroundQueueForBattlegroundQueueType(queue))
        {
            ++participants[key];
            TC_LOG_DEBUG("playerbots.bg", "Bot={} GUID={} queue_action=joined bracket={} team={}",
                bot->GetName(), bot->GetGUID().GetCounter(), uint32(bracket->GetBracketId()), uint32(bot->GetTeamId()));
        }
    }
}

bool ArathiBasinPlayerbot::DoNextAction(PlayerbotAI* ai)
{
    if (!Eligible(ai))
        return false;

    Player* bot = ai->GetBot();
    State& state = ai->GetArathiBasinState();
    Battleground* bg = bot->GetBattleground();
    if (!bg || bg->GetTypeID() != BATTLEGROUND_AB || bg->IsRated())
    {
        if (state.objectiveInstance)
            ResetObjective(state);
        return false;
    }
    if (!HasActiveBattlegroundMap(bot, bg))
        return false;
    if (bg->GetStatus() != STATUS_IN_PROGRESS || !bot->IsAlive())
    {
        if (!bot->IsAlive() && state.wasAlive)
            ResetApproach(state);
        state.wasAlive = bot->IsAlive();
        return false;
    }

    if (state.objectiveInstance != bg->GetInstanceID())
    {
        ResetObjective(state);
        state.objectiveInstance = bg->GetInstanceID();
        state.team = bot->GetBGTeam();
    }
    else if (!state.wasAlive)
        ResetApproach(state);
    state.wasAlive = true;
    state.team = bot->GetBGTeam();

    if (bot->isAFK())
        bot->ToggleAFK();

    uint32 now = getMSTime();
    SelectObjective(bot, bg, state, now);
    if (bot->IsInCombat() || ai->GetState() == BOT_STATE_COMBAT)
    {
        if (CombatSeparationMovement(ai, state, now).Execute(Event()))
        {
            ai->SetNextCheckDelay(1000);
            return true;
        }
        return false;
    }
    if (bot->HasUnitState(UNIT_STATE_CASTING))
    {
        ai->SetNextCheckDelay(500);
        return true;
    }

    AttackEnemyPlayerAction attack(ai);
    if (attack.isUseful() && attack.Execute(Event()))
        return false;

    BannerInfo banner = FindBanner(bg, state.objective);
    if (bot->IsMounted() && banner.object && !IsFriendlyBanner(bot, banner.type)
        && bot->GetDistance2d(banner.object) <= 12.0f)
    {
        WorldPacket packet(CMSG_CANCEL_MOUNT_AURA);
        bot->GetSession()->HandleCancelMountAuraOpcode(packet);
    }

    UseBanner(bot, bg, state, now);
    if (!bot->HasUnitState(UNIT_STATE_CASTING))
        ObjectiveMovement(ai, bg, state, now).Execute(Event());
    ai->SetNextCheckDelay(1000);
    return true;
}
