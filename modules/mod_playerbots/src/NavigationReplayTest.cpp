// Opt-in, console-only native query replay. Never relocates or dispatches movement.
#include "NavigationReplayTest.h"

#include "Chat.h"
#include "AiObjectContext.h"
#include "Config.h"
#include "Map.h"
#include "PathGenerator.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "LastMovementValue.h"
#include "MovementActions.h"

#include <array>
#include <cmath>

bool HandleNavigationReplayTest(ChatHandler* handler)
{
    if (handler->GetSession() || !sConfigMgr->GetBoolDefault("AiPlayerbot.NavigationReplayTest", false))
        return false;

    struct Replay
    {
        uint32 guid;
        G3D::Vector3 start, goal;
        float bodyHeight;
    };
    // Recorded dry-player primary queries from water-fix-20261108.
    std::array<Replay, 3> const cases{{
        {19, {909.1676f, 841.718f, -61.20891f}, {808.7228f, 873.2199f, -56.36741f}, 1.01564f},
        {19, {951.56573f, 830.5182f, -61.94283f}, {808.7228f, 873.2199f, -56.36741f}, 1.01564f},
        {6, {861.5789f, 842.38586f, -58.488213f}, {1150.173f, 842.5491f, -110.52471f}, 0.63261503f}
    }};
    // Check every source before doing any queries; retrying a not-ready fixture
    // must not emit a partial result mistaken for complete coverage.
    for (Replay const& test : cases)
    {
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(ObjectGuid::Create<HighGuid::Player>(test.guid));
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || ai->IsRealPlayer() || !bot->IsInWorld() || bot->GetMapId() != 529
            || !bot->InBattleground() || bot->IsBeingTeleported() || !bot->IsAlive()
            || bot->CanFly() || bot->IsFalling() || bot->GetTransport() || bot->GetVehicle()
            || bot->IsInWater() || bot->HasAuraType(SPELL_AURA_WATER_WALK) || bot->HasAuraType(SPELL_AURA_GHOST)
            || std::fabs(bot->GetCollisionHeight() * 0.5f - test.bodyHeight) > 0.0001f)
        {
            TC_LOG_INFO("playerbots", "Navigation replay waiting guid={}", test.guid);
            return true;
        }
    }

    uint32 index = 0;
    for (Replay const& test : cases)
    {
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(ObjectGuid::Create<HighGuid::Player>(test.guid));
        G3D::Vector3 const actual(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ());
        bot->GetMap()->LoadGrid(test.start.x, test.start.y);
        bot->GetMap()->LoadGrid(test.goal.x, test.goal.y);
        // Historical logs did not retain travel speeds. Record the live value
        // and probe ordinary unmounted/mounted costs explicitly, never mutate
        // the player's speeds or claim an unrecorded historical value is exact.
        std::array<float, 3> const speeds{{bot->GetSpeed(MOVE_RUN), 7.0f, 14.0f}};
        for (uint32 variant = 0; variant < speeds.size(); ++variant)
        {
            PathGenerator path(bot, 4096);
            path.SetUseWaterShortcut(false);
            path.SetTravelSpeeds(speeds[variant], bot->GetSpeed(MOVE_SWIM));
            bool const calculated = path.CalculatePath(test.goal.x, test.goal.y, test.goal.z,
                false, false, false, &test.start);
            auto const& points = path.GetPath();
            TC_LOG_INFO("playerbots", "Navigation replay case={} variant={} guid={} map={} instance={} from=({},{},{}) goal=({},{},{}) actual=({},{},{}) run={} swim={} bodyHeight={} minWaterHeight={} phaseMask={} calculated={} pathType={} queryStatus={} queryNodes={} reason={} points={} endOffset={}",
                index, variant, test.guid, bot->GetMapId(), bot->GetInstanceId(),
                test.start.x, test.start.y, test.start.z, test.goal.x, test.goal.y, test.goal.z,
                actual.x, actual.y, actual.z, speeds[variant], bot->GetSpeed(MOVE_SWIM),
                bot->GetCollisionHeight() * 0.5f, bot->GetMinHeightInWater(), bot->GetPhaseMask(),
                calculated, uint32(path.GetPathType()), path.GetPathQueryStatus(), path.GetPathQueryNodeLimit(),
                path.GetPathFailureReason(), points.size(), points.empty() ? -1.0f : (points.back() - test.goal).length());
        }
        if (sConfigMgr->GetBoolDefault("AiPlayerbot.NavigationReplayPlanner", false))
        {
            PlayerbotAI* ai = sPlayerbotsMgr->GetPlayerbotAI(bot);
            LastMovement& last = ai->GetAiObjectContext()->GetValue<LastMovement&>("last movement")->Get();
            struct RestoreMovementState
            {
                LastMovement& original;
                LastMovement saved;
                explicit RestoreMovementState(LastMovement& value) : original(value) { saved = value; }
                ~RestoreMovementState() { original = saved; }
            } restore(last);
            last.navigationDetour = {};
            last.navigationLogStarted = false;
            MovementAction planner(ai, "navigation replay");
            bool navigation = true;
            auto points = planner.SearchForBestPath(test.goal.x, test.goal.y, test.goal.z, navigation, true, 0, &test.start);
            bool valid = navigation && points.size() >= 2 && (points.front() - test.start).length() <= 0.1f;
            for (size_t i = 1; valid && i < points.size(); ++i)
                valid = planner.ValidateGroundConnection(points[i - 1], points[i])
                    || planner.ValidateWaterConnection(points[i - 1], points[i]);
            float const remaining = points.empty() ? -1.0f : (points.back() - test.goal).length();
            valid = valid && remaining < (test.start - test.goal).length();
            TC_LOG_INFO("playerbots", "Navigation replay planner case={} valid={} navigation={} points={} endOffset={} endpoint=({},{},{}) run={} swim={} relocated=0 dispatched=0",
                index, valid, navigation, points.size(), remaining,
                points.empty() ? 0.0f : points.back().x, points.empty() ? 0.0f : points.back().y,
                points.empty() ? 0.0f : points.back().z, bot->GetSpeed(MOVE_RUN), bot->GetSpeed(MOVE_SWIM));
        }
        if (bot->GetPositionX() != actual.x || bot->GetPositionY() != actual.y || bot->GetPositionZ() != actual.z)
        {
            TC_LOG_ERROR("playerbots", "Navigation replay failed: source moved during synchronous query");
            return false;
        }
        ++index;
    }
    TC_LOG_INFO("playerbots", "Navigation replay completed cases={} queries={} relocated=0 dispatched=0", index, index * 3);
    return true;
}

bool HandleNavigationStartMismatchReplayTest(ChatHandler* handler)
{
    if (handler->GetSession() || !sConfigMgr->GetBoolDefault("AiPlayerbot.NavigationReplayTest", false))
        return false;

    uint32 constexpr guid = 48;
    G3D::Vector3 const start(2840.988f, 3249.5918f, 432.9927f);
    G3D::Vector3 const goal(2841.4165f, 3249.3403f, 435.68625f);
    Player* bot = sRandomPlayerbotMgr->GetPlayerBot(ObjectGuid::Create<HighGuid::Player>(guid));
    PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
    G3D::Vector3 const actual = bot ? G3D::Vector3(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ())
                                         : G3D::Vector3();
    if (!bot || !ai || ai->IsRealPlayer() || !bot->IsInWorld() || bot->GetMapId() != 870
        || bot->GetInstanceId() || bot->IsBeingTeleported() || !bot->IsAlive()
        || bot->CanFly() || bot->IsFalling() || bot->GetTransport() || bot->GetVehicle()
        || bot->IsInWater() || bot->HasAuraType(SPELL_AURA_WATER_WALK) || bot->HasAuraType(SPELL_AURA_GHOST)
        || (actual - start).length() > 0.01f)
    {
        TC_LOG_INFO("playerbots", "Navigation start-mismatch replay waiting guid={} loaded={} map={} instance={} distance={}",
            guid, bot != nullptr, bot ? bot->GetMapId() : 0, bot ? bot->GetInstanceId() : 0,
            bot ? (actual - start).length() : -1.0f);
        return true;
    }

    bot->GetMap()->LoadGrid(start.x, start.y);
    bot->GetMap()->LoadGrid(goal.x, goal.y);
    PathGenerator nativePath(bot, 4096);
    bool const calculated = nativePath.CalculatePath(goal.x, goal.y, goal.z, false, false, false, &start);
    Movement::PointsArray const& nativePoints = nativePath.GetPath();
    float const startOffset = nativePoints.empty() ? -1.0f : (nativePoints.front() - start).length();

    float collisionX = goal.x;
    float collisionY = goal.y;
    float collisionZ = goal.z;
    bool const collisionOnly = bot->GetMap()->CheckCollisionAndGetValidCoords(bot, start.x, start.y, start.z,
        collisionX, collisionY, collisionZ, true);
    float slopeX = goal.x;
    float slopeY = goal.y;
    float slopeZ = goal.z;
    bool const slopeSafe = bot->GetMap()->CanReachPositionAndGetValidCoords(bot, start.x, start.y, start.z,
        slopeX, slopeY, slopeZ, true, true);

    LastMovement& last = ai->GetAiObjectContext()->GetValue<LastMovement&>("last movement")->Get();
    struct RestoreMovementState
    {
        LastMovement& original;
        LastMovement saved;
        explicit RestoreMovementState(LastMovement& value) : original(value) { saved = value; }
        ~RestoreMovementState() { original = saved; }
    } restore(last);
    last.navigationDetour = {};
    last.navigationLogStarted = false;
    MovementAction planner(ai, "navigation slope replay");
    bool navigation = true;
    Movement::PointsArray const planned = planner.SearchForBestPath(goal.x, goal.y, goal.z, navigation,
        false, 0, &start);

    bool const unchanged = bot->GetPositionX() == actual.x && bot->GetPositionY() == actual.y
        && bot->GetPositionZ() == actual.z;
    bool const passed = calculated && startOffset > 2.3f && collisionOnly && !slopeSafe
        && navigation && planned.empty() && unchanged;
    TC_LOG_INFO("playerbots", "Navigation start-mismatch replay guid={} passed={} calculated={} pathType={} reason={} points={} startOffset={} collisionOnly={} collisionEndpoint=({},{},{}) slopeSafe={} slopeEndpoint=({},{},{}) plannerNavigation={} plannerPoints={} actual=({},{},{}) relocated=0 dispatched=0",
        guid, passed, calculated, uint32(nativePath.GetPathType()), nativePath.GetPathFailureReason(),
        nativePoints.size(), startOffset, collisionOnly, collisionX, collisionY, collisionZ,
        slopeSafe, slopeX, slopeY, slopeZ, navigation, planned.size(), actual.x, actual.y, actual.z);
    if (!passed)
        return false;

    TC_LOG_INFO("playerbots", "Navigation start-mismatch replay completed cases=1 queries=4 relocated=0 dispatched=0");
    return true;
}
