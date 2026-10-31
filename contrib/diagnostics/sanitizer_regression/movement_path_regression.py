#!/usr/bin/env python3
"""Execute actual movement/path methods with controlled map and path doubles.

Tests dispatch, combat contact selection, endpoint bookkeeping and non-Unit
safety, not Detour geometry or client movement. Those still require an in-game
run. Use --verify-mutations to check the combat range/LOS/retry assertions.
"""

import os
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def method(path, signature):
    source = (root / path).read_text(encoding="utf-8-sig")
    begin = source.index(signature)
    brace = source.index("{", begin)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


move = method("modules/mod_playerbots/src/strategy/actions/MovementActions.cpp",
              "bool MovementAction::MoveTo(uint32 mapId,")
calculate = method("src/server/game/Movement/PathGenerator.cpp",
                   "bool PathGenerator::CalculatePath(")
reach_combat = method("modules/mod_playerbots/src/strategy/actions/MovementActions.cpp",
                      "bool MovementAction::ReachCombatTo(Unit* target, float distance)")
reach_useful = method("modules/mod_playerbots/src/strategy/actions/ReachTargetActions.cpp",
                      "bool ReachTargetAction::isUseful()")
melee_reposition = method("src/server/game/Entities/Unit/Unit.cpp",
                          "bool Unit::GetMeleeRepositionPoint(Unit const* attacker, Position& position) const")
assert "GetMeleeRepositionPoint" in reach_combat
assert "% 16U" in reach_combat
assert "GetMeleeRepositionPoint" in reach_useful
assert "!other->ToCreature()" not in melee_reposition
action_header = (root / "modules/mod_playerbots/src/strategy/actions/MovementActions.h").read_text()
failure_fields = action_header[action_header.index("    enum class MoveFailure"):
                               action_header.index("    void UpdateMovementState();")]

source = r"""
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>
using uint32 = std::uint32_t;
using PathType = int;
constexpr float INVALID_HEIGHT = -100000.0f;
constexpr float CONTACT_DISTANCE = 0.5f;
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
constexpr int UNIT_STATE_IGNORE_PATHFINDING = 1, UNIT_STAND_STATE_STAND = 0;
constexpr int MOVE_RUN = 0, MOVE_RUN_BACK = 1;
constexpr int MAP_ALL_LIQUIDS = 15, MAP_LIQUID_STATUS_IN_CONTACT = 1;
constexpr int PATHFIND_BLANK = 0, PATHFIND_NORMAL = 1, PATHFIND_SHORTCUT = 2, PATHFIND_INCOMPLETE = 4,
    PATHFIND_NOPATH = 8, PATHFIND_NOT_USING_PATH = 16, PATHFIND_SHORT = 32, PATHFIND_FARFROMPOLY = 192;
constexpr uint32 DT_OUT_OF_NODES=32, DT_BUFFER_TOO_SMALL=16;
namespace DisableMgr { bool enabled = true; bool IsPathfindingEnabled(uint32) { return enabled; } }
namespace G3D {
struct Vector3 {
    float x = 0, y = 0, z = 0;
    Vector3() = default;
    Vector3(float a, float b, float c) : x(a), y(b), z(c) {}
    Vector3 operator-(Vector3 const& b) const { return {x-b.x,y-b.y,z-b.z}; }
    float length() const { return std::sqrt(x*x+y*y+z*z); }
};
}
namespace Movement { using PointsArray = std::vector<G3D::Vector3>; }
namespace Trinity {
bool IsValidMapCoord(float x, float y, float z) {
    return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
}
}
struct Position {
    G3D::Vector3 point;
    Position(float x, float y, float z, float = 0) : point{x,y,z} {}
    void GetPosition(float& x, float& y, float& z) const { x=point.x; y=point.y; z=point.z; }
    float GetExactDist2d(float, float) const { return 100; }
};
struct Guid { uint32 value; uint32 GetCounter() const { return value; } };
struct Unit;
struct Vehicle;
struct WorldObject {
    Unit* unit = nullptr;
    G3D::Vector3 position;
    virtual ~WorldObject() = default;
    Unit const* ToUnit() const { return unit; }
    void GetPosition(float& x, float& y, float& z) const {
        x = position.x; y = position.y; z = position.z;
    }
    Position GetPosition() const { return {position.x,position.y,position.z}; }
    float GetPositionX() const { return position.x; }
    float GetPositionY() const { return position.y; }
    float GetPositionZ() const { return position.z; }
    void UpdateAllowedPositionZ(float, float, float& z) const { z = 5; }
    uint32 GetMapId() const { return 1; }
};
struct MotionMaster {
    int cleared = 0, moves = 0;
    bool backward = false, generated = false;
    G3D::Vector3 destination;
    void Clear() { ++cleared; }
    void MovePoint(uint32, float x, float y, float z, bool path) {
        ++moves; destination = {x,y,z}; generated = path; backward = false;
    }
    void MovePointBackwards(uint32 id, float x, float y, float z, bool path) {
        MovePoint(id,x,y,z,path); backward = true;
    }
    bool MovePointPath(uint32 id, Movement::PointsArray const& path) {
        MovePoint(id,path.back().x,path.back().y,path.back().z,true); return true;
    }
};
struct Map {
    bool liquid = false;
    float blockedX = std::numeric_limits<float>::quiet_NaN();
    bool isInLineOfSight(float x,float,float,float,float,float,uint32,VMAP::ModelIgnoreFlags) const {
        return !(std::fabs(x-blockedX)<0.01f);
    }
    int GetLiquidStatus(uint32, float, float, float, int, void*, float) const {
        return liquid ? MAP_LIQUID_STATUS_IN_CONTACT : 0;
    }
};
struct Unit : WorldObject {
    bool VisualizePathfinding = false, ignorePath = false;
    bool flying = false, water = false, sitting = false, battleground = false;
    bool los = true, reposition = false;
    uint32 guid = 1;
    float nearPointZ = std::numeric_limits<float>::quiet_NaN();
    Position repositionPoint{0,0,0};
    Vehicle* vehicle = nullptr;
    MotionMaster motion;
    Map map;
    Unit() { unit = this; }
    Guid GetGUID() const { return {guid}; }
    float GetCombatReach() const { return 1.5f; }
    bool IsWithinLOSInMap(Unit*) const { return los; }
    bool GetMeleeRepositionPoint(Unit*,Position& point) const {
        if (reposition) point=repositionPoint;
        return reposition;
    }
    void GetNearPoint(Unit* bot,float& x,float& y,float& z,float distance,float angle) const {
        float radius=GetCombatReach()+bot->GetCombatReach()+distance;
        x=position.x+radius*std::cos(angle); y=position.y+radius*std::sin(angle);
        z=std::isfinite(nearPointZ) ? nearPointZ : position.z;
    }
    bool HasUnitState(int) const { return ignorePath; }
    bool IsFlying() const { return flying; }
    bool CanFly() const { return flying; }
    bool IsUnderWater() const { return water; }
    bool IsInWater() const { return water; }
    bool InBattleground() const { return battleground; }
    bool IsSitState() const { return sitting; }
    void SetStandState(int) { sitting = false; }
    Vehicle* GetVehicle() const { return vehicle; }
    void* GetTransport() const { return nullptr; }
    Map* GetMap() { return &map; }
    uint32 GetPhaseMask() const { return 1; }
    float GetCollisionHeight() const { return 2; }
    MotionMaster* GetMotionMaster() { return &motion; }
    float GetSpeed(int) const { return 10; }
    float GetOrientation() const { return 0; }
    float GetExactDist(float x, float y, float z) const {
        return std::sqrt(std::pow(x-position.x,2) + std::pow(y-position.y,2) + std::pow(z-position.z,2));
    }
};
struct VehicleSeatEntry {
    bool control = true;
    bool CanControl() const { return control; }
};
struct Vehicle {
    Unit* base = nullptr;
    VehicleSeatEntry* seat = nullptr;
    VehicleSeatEntry const* GetSeatForPassenger(Unit*) const { return seat; }
    Unit* GetBase() const { return base; }
};
enum class MovementPriority { MOVEMENT_NORMAL, MOVEMENT_COMBAT, MOVEMENT_FORCED };
struct LastMovement {
    uint32 map = 0;
    G3D::Vector3 destination;
    float delay = 0;
    MovementPriority priority = MovementPriority::MOVEMENT_NORMAL;
    void Set(uint32 m, float x, float y, float z, float, float d, MovementPriority p) {
        map = m; destination = {x,y,z}; delay = d; priority = p;
    }
};
struct Config {
    int disableMoveSplinePath = 0, maxMovementSearchTime = 3, maxWaitForMove = 5000;
    float meleeDistance = 0.75f;
} config;
Config* sPlayerbotAIConfig = &config;
struct BotAI { int GetReactDelay() const { return 100; } } ai;
struct MovementAction {
    Unit* bot;
    BotAI* botAI = &ai;
    LastMovement last;
    Movement::PointsArray path = {{0,0,0}, {30,0,4}};
    std::vector<Movement::PointsArray> scriptedPaths;
    std::vector<G3D::Vector3> queries;
    float height = 4;
    bool allowed = true, duplicate = false, waiting = false, recoveryAllowed = true;
    bool lastGeneratePath = false, lastNormalOnly = false;
""" + failure_fields + r"""
    bool MoveTo(uint32,float,float,float,bool,bool,bool,bool,MovementPriority,bool,bool=false);
    bool ReachCombatTo(Unit*,float);
    void UpdateMovementState() {}
    bool IsMovingAllowed(uint32,float,float,float) const { return allowed; }
    bool IsMovingAllowed(Unit* target) const { return allowed && target; }
    bool IsDuplicateMove(uint32,float,float,float) const { return duplicate; }
    bool IsWaitingForLastMove(MovementPriority) const { return waiting; }
    bool CanStartGroundMovement(float,float,float) const { return recoveryAllowed; }
    void TrackGroundMovement(float,float,float,bool,bool) {}
    float MoveDelay(float distance, bool) const { return distance / 10; }
    Movement::PointsArray SearchForBestPath(float x,float y,float z,bool& generate,bool normal) {
        lastGeneratePath=generate;lastNormalOnly=normal;
        queries.push_back({x,y,z});
        if (!scriptedPaths.empty()) {
            auto result=scriptedPaths.front(); scriptedPaths.erase(scriptedPaths.begin()); return result;
        }
        return path;
    }
    void LogNavigationResult(char const*,char const*,uint32,uint32,float,float,float,bool) {}
};
#define AI_VALUE(type, name) last
#define TC_LOG_DEBUG(...) do {} while (false)
struct PathGenerator {
    WorldObject const* _source;
    bool _navMesh = true, _navMeshQuery = true, _forceDestination = false, tiles = true;
    int _type = PATHFIND_BLANK, built = 0, shortcuts = 0, filters = 0, visualized = 0;
    char const* _failureReason = nullptr;
    uint32 _queryStatus = 0;
    G3D::Vector3 start, end;
    explicit PathGenerator(WorldObject const* source) : _source(source) {}
    bool CalculatePath(float,float,float,bool,bool,bool,G3D::Vector3 const* = nullptr);
    void SetEndPosition(G3D::Vector3 const& p) { end = p; }
    void SetStartPosition(G3D::Vector3 const& p) { start = p; }
    bool HaveTile(G3D::Vector3 const&) const { return tiles; }
    void BuildShortcut() { ++shortcuts; }
    void UpdateFilter() { ++filters; }
    void BuildPolyPath(G3D::Vector3 const&, G3D::Vector3 const&) { ++built; _type = PATHFIND_NORMAL; }
    void VisualizePath(int) { ++visualized; }
    void VisualizeNavmesh(int) { ++visualized; }
};
""" + move + "\n" + calculate + "\n" + reach_combat + r"""
bool same(G3D::Vector3 const& a, G3D::Vector3 const& b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}
bool moveBot(MovementAction& action, bool backward = false, bool exact = false) {
    return action.MoveTo(1,100,0,20,false,false,false,exact,
        MovementPriority::MOVEMENT_COMBAT,true,backward);
}
void movementTests() {
    // Partial routes: forward/backward dispatch and bookkeeping must agree.
    for (bool backward : {false,true}) {
        Unit bot;
        MovementAction action{&bot};
        action.lastMoveFailure = MovementAction::MoveFailure::Route;
        assert(moveBot(action,backward));
        assert(action.lastMoveFailure == MovementAction::MoveFailure::None);
        assert(same(bot.motion.destination,action.path.back()));
        assert(same(action.last.destination,action.path.back()));
        assert(bot.motion.generated);
        assert(action.last.priority == MovementPriority::MOVEMENT_COMBAT);
        assert(std::fabs(action.last.delay - (100 * std::sqrt(916.0f) - 100)) < 0.01f);
    }
    // No route or no progress must preserve the active movement generator.
    for (Movement::PointsArray path : {Movement::PointsArray{},
        Movement::PointsArray{{0,0,0}}, Movement::PointsArray{{0,0,0},{0,0,0}}}) {
        Unit bot;
        MovementAction action{&bot}; action.path = path;
        assert(!moveBot(action));
        assert(action.lastMoveFailure == (path.size() < 2 ? MovementAction::MoveFailure::Route
            : MovementAction::MoveFailure::None));
        assert(!bot.motion.cleared && !bot.motion.moves && !action.last.map);
    }
    // Full routes, timing clamps and existing movement gates stay intact.
    {
        Unit bot; bot.sitting = true;
        MovementAction action{&bot}; action.path.back() = {100,0,20};
        assert(moveBot(action) && !bot.sitting);
        assert(same(bot.motion.destination,{100,0,20}));
        assert(same(action.last.destination,{100,0,20}));
        assert(action.last.delay == config.maxWaitForMove);
    }
    {
        Unit bot;
        MovementAction action{&bot}; action.path.back() = {0.1f,0,0};
        assert(moveBot(action) && action.last.delay == 0);
    }
    for (int gate = 0; gate < 3; ++gate) {
        Unit bot;
        MovementAction action{&bot};
        action.allowed = gate != 0; action.duplicate = gate == 1; action.waiting = gate == 2;
        action.lastMoveFailure = MovementAction::MoveFailure::Route;
        assert(!moveBot(action) && !bot.motion.cleared && !action.last.map);
        assert(action.lastMoveFailure == MovementAction::MoveFailure::None);
    }
    {
        Unit bot;
        MovementAction action{&bot}; action.recoveryAllowed = false;
        assert(!moveBot(action));
        assert(action.lastMoveFailure == MovementAction::MoveFailure::RecoveryExhausted);
        assert(!bot.motion.cleared && !bot.motion.moves && !action.last.map);
    }
    // Explicit, flying, fully submerged and configured point branches retain destinations.
    for (int mode = 0; mode < 4; ++mode) {
        Unit bot; bot.flying = mode == 1; bot.water = mode == 2;
        bot.map.liquid = mode == 2;
        config.disableMoveSplinePath = mode == 3 ? 2 : 0;
        MovementAction action{&bot};
        action.path.back() = {100,0,20};
        assert(moveBot(action,false,mode == 0));
        assert(same(bot.motion.destination,{100,0,20}));
        assert(same(action.last.destination,{100,0,20}));
    }
    // Leaving water must use the mixed ground/water route, not one unchecked
    // direct spline through a bank or terrain surface.
    {
        Unit bot; bot.water = true; bot.map.liquid = false;
        MovementAction action{&bot};
        assert(moveBot(action) && bot.motion.generated);
        assert(same(bot.motion.destination, action.path.back()));
    }
    // Battleground bots always use normal ground navigation, even if a stale
    // flying flag or an underwater state would normally select a direct spline.
    {
        Unit bot;bot.battleground=true;bot.flying=true;bot.water=true;bot.map.liquid=true;
        MovementAction action{&bot};
        assert(moveBot(action) && bot.motion.generated);
        assert(action.lastGeneratePath && action.lastNormalOnly);
        assert(same(bot.motion.destination,action.path.back()));
    }
    config.disableMoveSplinePath = 0;
    for (bool flying : {false,true}) {
        Unit bot, base; base.flying = flying;
        VehicleSeatEntry seat;
        Vehicle vehicle{&base,&seat}; bot.vehicle = &vehicle;
        MovementAction action{&bot};
        assert(moveBot(action));
        assert(base.motion.generated == !flying && !bot.motion.moves);
        assert(same(base.motion.destination,{100,0,20}));
    }
    Unit bot;
    VehicleSeatEntry seat;
    Vehicle vehicle{nullptr,&seat}; bot.vehicle = &vehicle;
    MovementAction action{&bot};
    assert(!moveBot(action));
    Unit base; vehicle.base = &base; vehicle.seat = nullptr;
    assert(!moveBot(action));
    vehicle.seat = &seat; seat.control = false;
    assert(!moveBot(action) && !base.motion.moves);
}
void pathTests() {
    // GameObjects are valid sources for PathGenerator and have no Unit.
    WorldObject object;
    PathGenerator objectPath(&object);
    assert(objectPath.CalculatePath(10,20,30,false,false,false));
    assert(objectPath.built == 1 && !objectPath.visualized && !objectPath.shortcuts);
    for (bool visualize : {false,true}) {
        Unit unit; unit.VisualizePathfinding = visualize;
        PathGenerator path(&unit);
        assert(path.CalculatePath(10,20,30,true,false,true));
        assert(path.built == 1 && path.visualized == (visualize ? 2 : 0));
        assert(path._forceDestination && path.start.z == 5);
    }
    for (int mode = 0; mode < 4; ++mode) {
        Unit unit; unit.ignorePath = mode == 3;
        PathGenerator path(&unit);
        path._navMesh = mode != 0; path._navMeshQuery = mode != 1; path.tiles = mode != 2;
        assert(path.CalculatePath(10,20,30,false,false,false));
        assert(path.shortcuts == 1 && !path.built && !path.visualized);
        assert(path._type == (PATHFIND_NORMAL | PATHFIND_NOT_USING_PATH));
    }
    PathGenerator invalid(&object);
    assert(!invalid.CalculatePath(std::numeric_limits<float>::quiet_NaN(),0,0,false,false,false));
    assert(!invalid.built && !invalid.shortcuts);
    assert(std::string(invalid._failureReason) == "invalid-coordinates");
    G3D::Vector3 from{4,5,6};
    PathGenerator continuation(&object);
    assert(continuation.CalculatePath(10,20,30,false,false,false,&from));
    assert(same(continuation.start,from) && same(object.position,{0,0,0}));
    for (bool enabled : {false,true}) {
        DisableMgr::enabled = enabled;
        PathGenerator missing(&object); missing._navMesh = false;
        assert(missing.CalculatePath(10,20,30,false,false,false));
        assert(std::string(missing._failureReason) == (enabled ? "missing-navmesh" : "pathfinding-disabled"));
    }
}
void combatTests() {
    // Actual 8h-soak coordinates: the deterministic GUID lane is only 4.5cm
    // from the bot, but its terrain height leaves the opponent 5.85m away.
    // The old code repeatedly requested this lane until the match ended.
    {
        Unit bot,target; bot.battleground=true;
        bot.guid=70; target.guid=169;
        bot.position={1132.7568f,1216.7504f,-56.712738f};
        target.position={1136.0001f,1218.1334f,-52.00786f};
        target.nearPointZ=-56.69769f;
        MovementAction action{&bot};
        G3D::Vector3 reachable{1135.0f,1218.0f,-53.0f};
        action.scriptedPaths={{bot.position,reachable,target.position},{bot.position,reachable}};
        assert(action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.size()==2 && same(action.queries[0],target.position));
        assert(same(bot.motion.destination,reachable) && bot.motion.generated);
    }
    // Preferred lane can look in range before projection but yield no path,
    // as in same-XY height-only rejections. Or its real endpoint may be out
    // of combat range/LOS. Each gets exactly one checked target-corridor retry.
    for (int failure=0;failure<3;++failure) {
        Unit bot,target; bot.battleground=true; target.position={6,0,0};
        target.reposition=true; target.repositionPoint={3,0,0};
        MovementAction action{&bot};
        Movement::PointsArray preferred;
        if (failure==1) preferred={bot.position,{1,0,0}};
        if (failure==2) {
            preferred={bot.position,{3,1,0}};
            // Block only the projected endpoint, not the proposed candidate.
            bot.map.blockedX=3.1f; preferred.back().x=3.1f;
        }
        action.scriptedPaths={preferred,{bot.position,{4,0,0},target.position},
            {bot.position,{4,0,0}}};
        assert(action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.size()==3 && same(action.queries[1],target.position));
        assert(same(bot.motion.destination,{4,0,0}) && bot.motion.generated);
        assert(action.lastNormalOnly);
    }
    // A blocked preferred contact point must be rejected before pathfinding.
    {
        Unit bot,target; bot.battleground=true; target.position={6,0,0};
        target.reposition=true; target.repositionPoint={3,0,0}; bot.map.blockedX=3;
        MovementAction action{&bot};
        action.scriptedPaths={{bot.position,{4,0,0},target.position},{bot.position,{4,0,0}}};
        assert(action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.size()==2 && same(action.queries.front(),target.position));
    }
    // Both routes blocked: no movement, no direct fallback, no endless retry.
    {
        Unit bot,target; bot.battleground=true; target.position={6,0,0};
        target.reposition=true; target.repositionPoint={3,0,0};
        MovementAction action{&bot}; action.scriptedPaths={{},{}};
        assert(!action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.size()==2 && !bot.motion.moves && !bot.motion.cleared);
        assert(action.lastNormalOnly);
    }
    // Preserve a good contact reservation and partial target corridors.
    for (bool partial : {false,true}) {
        Unit bot,target; bot.battleground=true; target.position={6,0,0};
        target.reposition=true; target.repositionPoint={3,0,0};
        MovementAction action{&bot};
        if (partial) action.scriptedPaths={{},{bot.position,{1,0,0}},{bot.position,{1,0,0}}};
        else action.scriptedPaths={{bot.position,{3,0,0}},{bot.position,{3,0,0}}};
        assert(action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.size()==(partial?3:2));
        assert(same(bot.motion.destination,{partial?1.0f:3.0f,0,0}));
    }
    // Ranged approach must not stop at an in-range vertex behind a wall.
    {
        Unit bot,target; bot.battleground=true; target.position={12,0,0};
        bot.map.blockedX=6;
        MovementAction action{&bot};
        action.scriptedPaths={{bot.position,{6,0,0},{7,0,0},target.position},{bot.position,{7,0,0}}};
        assert(action.ReachCombatTo(&target,5));
        assert(same(bot.motion.destination,{7,0,0}));
    }
    // Already in range, absent target and movement restrictions need no query.
    {
        Unit bot,target; target.position={2,0,0};
        MovementAction action{&bot};
        assert(!action.ReachCombatTo(&target,config.meleeDistance));
        assert(!action.ReachCombatTo(nullptr,config.meleeDistance));
        action.allowed=false; target.position={20,0,0};
        assert(!action.ReachCombatTo(&target,config.meleeDistance));
        assert(action.queries.empty() && !bot.motion.moves);
    }
}
int main(int argc, char** argv) {
    assert(argc == 2);
    if (std::string(argv[1]) == "movement") movementTests();
    else if (std::string(argv[1]) == "combat") combatTests();
    else pathTests();
}
"""

with tempfile.TemporaryDirectory(prefix="loa-movement-path-regression-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run(
        [compiler, "-x", "c++", "-std=c++20", "-O1", "-g",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-",
         "-o", str(binary)], input=source, text=True, check=True,
    )
    results = [subprocess.run([str(binary), scenario]).returncode
               for scenario in ("movement", "path", "combat")]
    assert results == [0, 0, 0], f"movement/path/combat scenarios failed: {results}"
    if "--verify-mutations" in sys.argv[3:]:
        mutations = (
            ("unchecked-contact", "if (contactPoint && !canReachTargetFrom({tx, ty, tz}, distance))", "if (false)"),
            ("no-target-corridor-retry", "if (contactPoint && (path.size() < 2 || !canReachTargetFrom(path.back(), distance)))", "if (false)"),
            ("unchecked-combat-los", "bot->GetMap()->isInLineOfSight(point.x, point.y, point.z + bot->GetCollisionHeight(),\n"
             "                targetPosition.x, targetPosition.y, targetPosition.z + target->GetCollisionHeight(),\n"
             "                bot->GetPhaseMask(), VMAP::ModelIgnoreFlags::Nothing)", "true"),
        )
        environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        for label, original, changed in mutations:
            assert source.count(original) == 1, label
            subprocess.run([compiler, "-x", "c++", "-std=c++20", "-O1", "-g",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-", "-o", str(binary)],
                           input=source.replace(original, changed, 1), text=True, check=True)
            result = subprocess.run([str(binary), "combat"], env=environment, text=True, capture_output=True)
            assert result.returncode != 0 and "Assertion" in result.stderr, (label, result.stderr)
            print(f"Mutation {label}: rejected by assertion", flush=True)
print("Movement endpoint, combat approach and non-Unit path regression passed", flush=True)
