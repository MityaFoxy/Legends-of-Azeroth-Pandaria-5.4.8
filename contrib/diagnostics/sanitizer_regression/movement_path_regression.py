#!/usr/bin/env python3
"""Execute actual movement/path methods with controlled map and path doubles.

Tests dispatch, endpoint bookkeeping and non-Unit safety, not Detour geometry
or client movement. Those still require an in-game run.
"""

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
    Position(float, float, float, float) {}
    float GetExactDist2d(float, float) const { return 100; }
};
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
    int GetLiquidStatus(uint32, float, float, float, int, void*, float) const {
        return liquid ? MAP_LIQUID_STATUS_IN_CONTACT : 0;
    }
};
struct Unit : WorldObject {
    bool VisualizePathfinding = false, ignorePath = false;
    bool flying = false, water = false, sitting = false, battleground = false;
    Vehicle* vehicle = nullptr;
    MotionMaster motion;
    Map map;
    Unit() { unit = this; }
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
} config;
Config* sPlayerbotAIConfig = &config;
struct BotAI { int GetReactDelay() const { return 100; } } ai;
struct MovementAction {
    Unit* bot;
    BotAI* botAI = &ai;
    LastMovement last;
    Movement::PointsArray path = {{0,0,0}, {30,0,4}};
    float height = 4;
    bool allowed = true, duplicate = false, waiting = false;
    bool MoveTo(uint32,float,float,float,bool,bool,bool,bool,MovementPriority,bool,bool);
    void UpdateMovementState() {}
    bool IsMovingAllowed(uint32,float,float,float) const { return allowed; }
    bool IsDuplicateMove(uint32,float,float,float) const { return duplicate; }
    bool IsWaitingForLastMove(MovementPriority) const { return waiting; }
    bool CanStartGroundMovement(float,float,float) const { return true; }
    void TrackGroundMovement(float,float,float,bool,bool) {}
    float MoveDelay(float distance, bool) const { return distance / 10; }
    Movement::PointsArray SearchForBestPath(float,float,float,bool&,bool) {
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
""" + move + "\n" + calculate + r"""
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
        assert(moveBot(action,backward));
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
        assert(!moveBot(action) && !bot.motion.cleared && !action.last.map);
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
int main(int argc, char** argv) {
    assert(argc == 2);
    if (std::string(argv[1]) == "movement") movementTests();
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
               for scenario in ("movement", "path")]
    assert results == [0, 0], f"movement/path scenarios failed: {results}"
print("Movement endpoint and non-Unit path regression passed", flush=True)
