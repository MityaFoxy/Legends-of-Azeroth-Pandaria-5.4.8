#!/usr/bin/env python3
"""Exercise actual route selection, logging and point-path execution with doubles.

The scripted queries test policy, not real mmap topology or client movement.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
map_source = (root / "src/server/game/Maps/Map.cpp").read_text()
assert "z < ground_level - GROUND_HEIGHT_TOLERANCE" in map_source
# A tiny spline normalization error must retain water state, while a genuinely
# subterranean point must not be reclassified as water.
ground, tolerance = -77.36180, 0.05
assert not (-77.37672 < ground - tolerance)
assert -78.0 < ground - tolerance


def method(path, signature):
    source = (root / path).read_text(encoding="utf-8-sig")
    begin = source.index(signature)
    brace = source.index("{", begin)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


action_path = "modules/mod_playerbots/src/strategy/actions/MovementActions.cpp"
point_path = "src/server/game/Movement/MovementGenerators/PointMovementGenerator.cpp"
methods = [method(action_path, signature) for signature in (
    "bool MovementAction::ValidateWaterConnection(", "bool MovementAction::ValidateGroundConnection(",
    "void MovementAction::LogNavigationResult(", "Movement::PointsArray MovementAction::SearchForBestPath(",
    "bool MovementAction::CanStartGroundMovement(", "void MovementAction::TrackGroundMovement(",
    "void MovementAction::LogStuckResult(", "void MovementAction::CheckStuck(")]
methods += ["template<class T>\n" + method(point_path, signature) for signature in (
    "bool PointMovementGenerator<T>::DoInitialize(", "bool PointMovementGenerator<T>::DoUpdate(")]
methods += [method("src/server/game/Movement/MotionMaster.cpp", "bool MotionMaster::MovePointPath(")]
state_source = (root / "modules/mod_playerbots/src/strategy/value/GroundMovementState.h").read_text()
state_source = "\n".join(line for line in state_source.splitlines() if not line.startswith("#"))
# Integration guard: observation must not disappear behind action wait/duplicate gates.
ai_update = method("modules/mod_playerbots/src/AI/PlayerbotAI.cpp", "void PlayerbotAI::UpdateAI(")
assert ai_update.index("CheckStuck(elapsed)") < ai_update.index("if (!CanUpdateAI())")
move_to = method(action_path, "bool MovementAction::MoveTo(uint32 mapId,")
assert move_to.index("CanStartGroundMovement(") < move_to.index("IsDuplicateMove(")
assert "TrackGroundMovement(x, y, z, normal_only, backwards)" in move_to

source = r"""
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <deque>
#include <limits>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
using uint32 = std::uint32_t;
using int32 = std::int32_t;
using PathType = int;
constexpr int PATHFIND_BLANK=0, PATHFIND_NORMAL=1, PATHFIND_SHORTCUT=2, PATHFIND_INCOMPLETE=4,
    PATHFIND_NOPATH=8, PATHFIND_NOT_USING_PATH=16, PATHFIND_SHORT=32,
    PATHFIND_FARFROMPOLY_START=64, PATHFIND_FARFROMPOLY_END=128, MAX_POINT_PATH_LENGTH=200;
constexpr float INVALID_HEIGHT=-100000;
constexpr int UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2, UNIT_STATE_ROAMING=4, UNIT_STATE_ROAMING_MOVE=8, UNIT_STATE_LOST_CONTROL=16;
constexpr int TYPEID_UNIT=0, TYPEID_PLAYER=1, EVENT_CHARGE_PREPATH=99;
constexpr int POINT_MOTION_TYPE=1, CHASE_MOTION_TYPE=2, MOVE_RUN=0, MOVE_RUN_BACK=1, MOVEMENTFLAG_SWIMMING=8;
constexpr int MOVE_SWIM=2, MOVE_SWIM_BACK=3, LIQUID_MAP_NO_WATER=0, LIQUID_MAP_UNDER_WATER=8;
constexpr int MAP_ALL_LIQUIDS=15, MAP_LIQUID_STATUS_IN_CONTACT=14;
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
struct LiquidData { float level=1, depth_level=-10; };
using MovementSlot = int;
constexpr MovementSlot MOTION_SLOT_ACTIVE=1;
uint32 tick=100;
uint32 getMSTime() { return tick; }
uint32 getMSTimeDiff(uint32 before,uint32 after) { return after-before; }
namespace G3D {
struct Vector3 {
    float x=0,y=0,z=0;
    Vector3()=default;
    Vector3(float a,float b,float c):x(a),y(b),z(c) {}
    Vector3 operator-(Vector3 const& b) const { return {x-b.x,y-b.y,z-b.z}; }
    Vector3 operator+(Vector3 const& b) const { return {x+b.x,y+b.y,z+b.z}; }
    Vector3 operator*(float value) const { return {x*value,y*value,z*value}; }
    float length() const { return std::sqrt(x*x+y*y+z*z); }
};
}
bool same(G3D::Vector3 const& a,G3D::Vector3 const& b) { return (a-b).length()<0.001f; }
namespace Movement { using PointsArray=std::vector<G3D::Vector3>; }
namespace Trinity {
bool IsValidMapCoord(float x,float y,float z) { return std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z); }
}
struct Creature;
struct Formation { Creature* GetLeader() const { return nullptr; } void LeaderStartedMoving() {} };
struct Creature { Formation* GetFormation() const { return nullptr; } };
struct Guid { uint32 GetCounter() const { return 7; } };
struct Map {
    bool collision=true, liquid=false, los=true, liquidGap=false;
    LiquidData waterData;
    int GetLiquidStatus(uint32,float x,float,float,int,LiquidData* data,float) const {
        if (data) *data=waterData;
        return liquid && !(liquidGap && x>2 && x<3) ? MAP_LIQUID_STATUS_IN_CONTACT : LIQUID_MAP_NO_WATER;
    }
    bool isInLineOfSight(float,float,float,float,float,float,uint32,VMAP::ModelIgnoreFlags) const { return los; }
    bool CheckCollisionAndGetValidCoords(void const*,float,float,float,float& x,float& y,float& z,bool=true) const {
        (void)x;(void)y;(void)z; return collision;
    }
};
struct Spline {
    int index=0, launches=0, direct=0;
    bool finalized=false;
    Movement::PointsArray points;
    int currentPathIdx() const { return index; }
    bool Finalized() const { return finalized; }
    uint32 id=1;
    uint32 GetId() const { return id; }
    G3D::Vector3 FinalDestination() const { return points.empty() ? G3D::Vector3{100,0,0} : points.back(); }
};
struct MotionMaster;
struct Unit {
    G3D::Vector3 position;
    bool transport=false, invalidHeight=false, stopped=true;
    int state=0;
    uint32 map=1,instance=2;
    bool flying=false,water=false,swimming=false,vehicle=false,teleport=false,alive=true,casting=false,sitting=false;
    bool canSwim=true;
    float speed=7, swimSpeed=4, groundHeight=0;
    mutable int lastSpeedMode=MOVE_RUN;
    Map mapObject;
    MotionMaster* motion=nullptr;
    Spline spline;
    Spline* movespline=&spline;
    float GetPositionX() const { return position.x; }
    float GetPositionY() const { return position.y; }
    float GetPositionZ() const { return position.z; }
    uint32 GetMapId() const { return map; }
    uint32 GetInstanceId() const { return instance; }
    Guid GetGUID() const { return {}; }
    Map* GetMap() { return &mapObject; }
    uint32 GetPhaseMask() const { return 1; }
    float GetCollisionHeight() const { return 2; }
    void* GetTransport() const { return transport ? (void*)this : nullptr; }
    float GetMapHeight(float,float,float,bool=true,float=50) const { return invalidHeight ? INVALID_HEIGHT : groundHeight; }
    bool IsStopped() const { return stopped; }
    void StopMoving() { stopped=true; }
    MotionMaster* GetMotionMaster() const { return motion; }
    void* GetVehicle() const { return vehicle ? (void*)this : nullptr; }
    bool IsFlying() const { return flying; }
    bool IsInWater() const { return water; }
    bool IsUnderWater() const { return water; }
    bool HasUnitMovementFlag(int flag) const { assert(flag==MOVEMENTFLAG_SWIMMING); return swimming; }
    bool CanSwim() const { return canSwim; }
    bool SetSwim(bool value) { bool changed=swimming!=value; swimming=value; return changed; }
    bool IsBeingTeleported() const { return teleport; }
    bool IsAlive() const { return alive; }
    bool IsNonMeleeSpellCasted(bool) const { return casting; }
    bool IsSitState() const { return sitting; }
    float GetSpeed(int mode) const {
        lastSpeedMode=mode;
        return mode==MOVE_SWIM || mode==MOVE_SWIM_BACK ? swimSpeed : speed;
    }
    float GetOrientation() const { return 0; }
    void AddUnitState(int flags) { state|=flags; }
    void ClearUnitState(int flags) { state&=~flags; }
    bool HasUnitState(int flags) const { return state&flags; }
    Creature* ToCreature() const { return nullptr; }
    int GetTypeId() const { return TYPEID_PLAYER; }
};
using Player=Unit;
namespace Movement {
struct MoveSplineInit {
    Unit* unit;
    PointsArray points;
    explicit MoveSplineInit(Unit* u):unit(u) {}
    void MoveTo(float x,float y,float z,bool) { ++unit->spline.direct; points={unit->position,{x,y,z}}; }
    void MovebyPath(PointsArray const& p) { points=p; }
    void SetVelocity(float) {}
    void Launch() {
        points.front()=unit->position; unit->spline.points=points;
        ++unit->spline.launches; unit->spline.index=0;
    }
};
}
struct MovementGenerator { virtual ~MovementGenerator()=default; };
template<class T> struct PointMovementGenerator : MovementGenerator {
    uint32 id;
    float i_x,i_y,i_z,speed=0;
    bool m_generatePath=false,i_recalculateSpeed=false;
    Movement::PointsArray _precomputedPath;
    PointMovementGenerator(uint32 i,float x,float y,float z,bool generate):id(i),i_x(x),i_y(y),i_z(z),m_generatePath(generate) {}
    void SetPrecomputedPath(Movement::PointsArray const& path) { _precomputedPath=path; }
    bool DoInitialize(T*);
    bool DoUpdate(T*,uint32);
    void MovementInform(T*) {}
};
struct MotionMaster {
    Unit* _owner;
    int mutations=0;
    std::unique_ptr<MovementGenerator> movement;
    int type=POINT_MOTION_TYPE,cleared=0,expired=0;
    int speedChanges=0;
    void PropagateSpeedChange() { ++speedChanges; }
    MovementGenerator* top() const { return movement.get(); }
    int GetCurrentMovementGeneratorType() const { return type; }
    void Clear() { ++cleared; movement.reset(); }
    void MovementExpired() { ++expired; movement.reset(); }
    void Mutate(MovementGenerator* m,MovementSlot) { ++mutations; movement.reset(m); }
    bool MovePointPath(uint32,Movement::PointsArray const&,MovementSlot=MOTION_SLOT_ACTIVE);
};
""" + state_source + r"""
struct LastMovement {
    uint32 navigationLogTime=0,navigationLogSuppressed=0;
    bool navigationLogStarted=false,navigationLogWarning=false;
    GroundMovementState groundMovement;
    NavigationDetourState navigationDetour;
    float lastdelayTime=5000;
    int priority=1;
    G3D::Vector3 destination;
    void Set(uint32,float x,float y,float z,float,float delay,int) { destination={x,y,z}; lastdelayTime=delay; }
};
struct Config { uint32 navigationMaxAttempts=5,navigationLogInterval=30000,stuckTimeout=4000,stuckMaxAttempts=3; } config;
Config* sPlayerbotAIConfig=&config;
struct MovementAction {
    Unit* bot;
    LastMovement last;
    bool ValidateWaterConnection(G3D::Vector3 const&,G3D::Vector3 const&);
    bool ValidateGroundConnection(G3D::Vector3 const&,G3D::Vector3 const&);
    Movement::PointsArray SearchForBestPath(float,float,float,bool&,bool=false,uint32=0);
    void LogNavigationResult(char const*,char const*,uint32,uint32,float,float,float,bool);
    bool CanStartGroundMovement(float,float,float);
    void TrackGroundMovement(float,float,float,bool,bool);
    void LogStuckResult(char const*,uint32,bool=true);
    void CheckStuck(uint32);
    bool IsMovingAllowed() const { return !bot->HasUnitState(UNIT_STATE_LOST_CONTROL); }
};
#define AI_VALUE(type,name) this->last
struct Row { std::string level,text; };
std::vector<Row> logs;
template<class... Args> void emit(char const* level,char const*,char const* format,Args... args) {
    std::ostringstream out;
    out << format << ' ';
    ((out << args << ' '),...);
    logs.push_back({level,out.str()});
}
#define TC_LOG_DEBUG(...) emit("debug",__VA_ARGS__)
#define TC_LOG_WARN(...) emit("warn",__VA_ARGS__)
#define TC_LOG_INFO(...) emit("info",__VA_ARGS__)
struct Route {
    int type=PATHFIND_NORMAL;
    bool calculated=true,data=true,automatic=true;
    char const* reason="none";
    Movement::PointsArray points;
};
std::deque<Route> replies;
struct Query { G3D::Vector3 from,to; float runSpeed,swimSpeed; };
std::vector<Query> queries;
struct PathGenerator {
    Unit* source;
    Route route;
    bool waterShortcut=true;
    float runSpeed=0,swimSpeed=0;
    explicit PathGenerator(Unit* u,uint32 nodes):source(u) { assert(nodes==4096); }
    void SetUseWaterShortcut(bool value) { waterShortcut=value; }
    void SetTravelSpeeds(float run,float swim) { runSpeed=run; swimSpeed=swim; }
    bool CalculatePath(float x,float y,float z,bool,bool,bool,G3D::Vector3 const* from) {
        assert(!waterShortcut && runSpeed>0 && swimSpeed>0);
        assert(!replies.empty()); route=replies.front(); replies.pop_front();
        queries.push_back({*from,{x,y,z},runSpeed,swimSpeed}); tick+=2;
        if (route.automatic) route.points={*from,{x,y,z}};
        return route.calculated;
    }
    int GetPathType() const { return route.type; }
    char const* GetPathFailureReason() const { return route.reason; }
    bool HasNavigationData() const { return route.data; }
    uint32 GetPathQueryStatus() const { return 0; }
    uint32 GetPathQueryNodeLimit() const { return 4096; }
    Movement::PointsArray const& GetPath() const { return route.points; }
};
""" + "\n".join(methods) + r"""
Route bad(char const* reason="no-path-or-mesh-hole") { Route r; r.type=PATHFIND_NOPATH; r.reason=reason; return r; }
void reset() { config={}; replies.clear(); queries.clear(); logs.clear(); tick=100; }
bool hasLog(char const* level,char const* text) {
    return std::any_of(logs.begin(),logs.end(),[&](Row const& r) {
        return r.level==level && r.text.find(text)!=std::string::npos;
    });
}
int summaries() { return std::count_if(logs.begin(),logs.end(),[](Row const& r){return r.level!="debug";}); }
void connectionTests() {
    reset(); Unit bot; MovementAction action{&bot};
    // These are production validators, not unconditional "safe" stubs.
    assert(action.ValidateGroundConnection({0,0,0},{3,0,0}));
    assert(!action.ValidateGroundConnection({0,0,0},{3.01f,0,0}));
    bot.mapObject.los=false;
    assert(!action.ValidateGroundConnection({0,0,0},{2,0,0}));
    bot.mapObject.los=true; bot.invalidHeight=true;
    assert(!action.ValidateGroundConnection({0,0,0},{2,0,0}));
    bot.invalidHeight=false; bot.groundHeight=-3;
    assert(!action.ValidateGroundConnection({0,0,0},{2,0,0}));
    bot.mapObject.liquid=true;
    assert(action.ValidateGroundConnection({0,0,0},{2,0,0})); // Supported by water at shore.
    assert(action.ValidateWaterConnection({0,0,0},{16,0,0}));
    assert(!action.ValidateWaterConnection({0,0,0},{16.01f,0,0}));
    bot.mapObject.liquidGap=true;
    assert(!action.ValidateWaterConnection({0,0,0},{6,0,0})); // Endpoints alone are insufficient.
    bot.mapObject.liquidGap=false; bot.mapObject.los=false;
    assert(!action.ValidateWaterConnection({0,0,0},{6,0,0}));
    bot.mapObject.los=true;
    assert(!action.ValidateWaterConnection({0,0,0},{0,0,-11})); // Below the bottom.
    assert(!action.ValidateWaterConnection({0,0,0},{0,0,2}));   // Above the allowed surface margin.
    bot.mapObject.waterData.level=std::numeric_limits<float>::quiet_NaN();
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    bot.mapObject.waterData={1,1};
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0})); // No liquid depth.
    bot.mapObject.waterData={}; bot.mapObject.liquid=false;
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
}

void waterAndProjectionTests() {
    reset(); Unit bot; MovementAction action{&bot}; bool navigation=false;
    bot.water=true; bot.mapObject.liquid=true;
    auto path=action.SearchForBestPath(10,0,0,navigation,true);
    assert(navigation && queries.empty() && same(path.back(),{10,0,0}));
    // An interrupted liquid volume cannot become a direct underwater shortcut.
    bot.mapObject.liquidGap=true; config.navigationMaxAttempts=1; replies={bad()};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty() && queries.size()==1);
    reset(); action.last={}; bot.mapObject.liquidGap=false; bot.mapObject.los=false;
    config.navigationMaxAttempts=1; replies={bad()};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty() && queries.size()==1);
    bot.mapObject.los=true;

    // A submerged path start may join its surface polygon, but only through
    // the short validated liquid volume. Preserve the actual starting point.
    reset(); action.last={};
    Route wet; wet.type=PATHFIND_INCOMPLETE|PATHFIND_FARFROMPOLY_START;
    wet.automatic=false; wet.points={{0,0,1},{100,0,0}}; replies={wet};
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(navigation && queries.size()==1 && path.size()==3 && same(path.front(),bot.position));
    reset(); action.last={}; wet.points.front()={0,0,3};
    config.navigationMaxAttempts=1; replies={wet};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty());

    // Surface-normalization failure triggers one land-preferred retry inside
    // the SAME query budget, with water shortcuts still disabled.
    reset(); action.last={}; replies={bad("unsafe-surface-normalization"),Route{}};
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(navigation && queries.size()==2 && same(path.back(),{100,0,0}));
    assert(queries[0].swimSpeed==bot.swimSpeed && queries[1].swimSpeed==0.01f);
    reset(); action.last={}; config.navigationMaxAttempts=1;
    replies={bad("unsafe-surface-normalization")};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty() && queries.size()==1);

    // The formerly rejected 2m start offset is now valid IF supported and
    // unobstructed; a wall or missing terrain must still reject it.
    bot.water=false; bot.mapObject.liquid=false;
    Route projected; projected.automatic=false; projected.points={{2,0,0},{100,0,0}};
    reset(); action.last={}; replies={projected};
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(path.size()==3 && same(path.front(),bot.position) && queries.size()==1);
    reset(); action.last={}; bot.invalidHeight=true; config.navigationMaxAttempts=1; replies={projected};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty()); bot.invalidHeight=false;
    reset(); action.last={}; bot.mapObject.los=false; config.navigationMaxAttempts=1; replies={projected};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
}

void searchTests() {
    reset(); Unit bot; MovementAction action{&bot}; bool navigation=false;
    replies={Route{}};
    auto path=action.SearchForBestPath(100,0,0,navigation);
    assert(queries.size()==1 && navigation && same(path.back(),{100,0,0}) && summaries()==0);

    // Primary and first complete detour fail; the opposite two-leg detour succeeds.
    reset(); action.last={}; replies={bad(),Route{},bad(),Route{},Route{}};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(queries.size()==5 && navigation && path.size()==3);
    assert(same(path.back(),{100,0,0}) && path[1].y<0);
    assert(same(queries[2].from,queries[1].to) && same(queries[4].from,queries[3].to));
    assert(queries[1].to.y>0 && queries[3].to.y<0 && same(bot.position,{0,0,0}));
    assert(hasLog("info","alternative-route"));

    // A reachable intermediate point is NOT a complete alternative.
    reset(); action.last={}; Route incomplete; incomplete.type=PATHFIND_INCOMPLETE;
    replies={bad(),Route{},incomplete,Route{},bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(!navigation && path.size()==2 && same(path.back(),{8,0,0}));
    assert(hasLog("warn","fallback-direct"));
    reset(); action.last={}; replies={bad(),Route{},incomplete,Route{},bad()};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
    assert(hasLog("warn","rejected"));

    // Missing global mesh/query cannot be repaired by more search requests.
    reset(); action.last={}; Route missing=bad("missing-navmesh"); missing.data=false;
    replies={missing}; path=action.SearchForBestPath(100,0,0,navigation);
    assert(queries.size()==1 && !navigation && same(path.back(),{8,0,0}) && hasLog("warn","missing-navmesh"));

    // A submerged start may bridge a small vertical gap to the water polygon;
    // this is preferable to a long unchecked spline through the river bank.
    reset(); action.last={}; bot.mapObject.liquid=true;
    Route wet; wet.type=PATHFIND_INCOMPLETE|PATHFIND_FARFROMPOLY_START;
    wet.reason="far-from-navigation-polygon"; replies={wet};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(navigation && queries.size()==1 && same(path.back(),{100,0,0}));
    bot.mapObject.liquid=false;

    // Prefer useful partial navigation to direct fallback, but not no-progress paths.
    reset(); action.last={}; Route partial; partial.type=PATHFIND_INCOMPLETE;
    partial.automatic=false; partial.points={{0,0,0},{40,0,0}};
    replies={partial,bad(),bad(),bad(),bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(navigation && same(path.back(),{40,0,0}) && hasLog("warn","partial-route"));
    reset(); action.last={}; partial.points={{0,0,0},{0,0,0}};
    replies={partial,bad(),bad(),bad(),bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(!navigation && same(path.back(),{8,0,0}));

    // A nominally NORMAL path can still stop short after height normalization.
    reset(); action.last={}; partial.type=PATHFIND_NORMAL; partial.points={{0,0,0},{40,0,0}};
    replies={partial,bad(),bad(),bad(),bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(navigation && hasLog("warn","destination-not-reached"));
    reset(); action.last={}; partial.points={{4,0,0},{40,0,0}};
    replies={partial,bad(),bad(),bad(),bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(!navigation && same(path.back(),{8,0,0}) && hasLog("warn","path-start-mismatch"));
    reset(); action.last={}; partial.points={{0,0,0},{0,0,0}};
    replies={partial,bad(),bad(),bad(),bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(!navigation && same(path.back(),{8,0,0}) && hasLog("warn","path-no-progress"));

    // The last-resort step is still refused when collision validation cannot
    // prove even the short segment safe.
    reset(); action.last={}; bot.mapObject.collision=false; replies=std::deque<Route>(10,bad());
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(path.empty() && navigation && hasLog("warn","unsafe-direct-fallback"));
    bot.mapObject.collision=true;

    // The query budget is total calls, clamped, and missing terrain is not queried.
    for (uint32 limit : {0u,1u,2u,5u,10u,100u}) {
        reset(); action.last={}; config.navigationMaxAttempts=limit;
        replies=std::deque<Route>(20,bad());
        path=action.SearchForBestPath(100,0,0,navigation);
        assert(queries.size()<=std::clamp(limit,1u,10u) && !navigation);
    }
    reset(); action.last={}; bot.invalidHeight=true; replies={bad()};
    path=action.SearchForBestPath(100,0,0,navigation);
    assert(queries.size()==1 && !navigation); bot.invalidHeight=false;

    // Bad path coordinates/start must not reach the point movement generator.
    for (Movement::PointsArray points : {Movement::PointsArray{}, Movement::PointsArray{{0,0,0}},
        Movement::PointsArray{{20,0,0},{100,0,0}},
        Movement::PointsArray{{0,0,0},{std::numeric_limits<float>::quiet_NaN(),0,0}}}) {
        reset(); action.last={}; config.navigationMaxAttempts=1;
        Route invalid; invalid.automatic=false; invalid.points=points; replies={invalid};
        assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
    }
    reset(); replies={};
    assert(action.SearchForBestPath(0,0,0,navigation).empty() && queries.empty());
}
void logTests() {
    reset(); Unit bot; MovementAction action{&bot};
    action.LogNavigationResult("alternative-route","no-path",8,3,100,0,0,false);
    action.LogNavigationResult("fallback-direct","missing-navmesh",16,1,100,0,0,true);
    assert(summaries()==2); // A recovery message must not hide the first fallback warning.
    action.LogNavigationResult("fallback-direct","missing-navmesh",16,1,100,0,0,true);
    assert(summaries()==2 && action.last.navigationLogSuppressed==1);
    tick+=30000;
    action.LogNavigationResult("fallback-direct","missing-navmesh",16,1,100,0,0,true);
    assert(summaries()==3 && logs.back().text.ends_with("1 "));
    action.last.navigationLogTime=std::numeric_limits<uint32>::max()-100;
    tick=100;
    action.LogNavigationResult("fallback-direct","missing-navmesh",16,1,100,0,0,true);
    assert(summaries()==3); // Unsigned server timer rollover must not defeat throttling.
    action.last={}; bot.water=true; bot.swimming=true;
    action.LogNavigationResult("fallback-direct","far-from-navigation-polygon",68,4,100,0,0,true);
    assert(logs.back().text.ends_with("1 1 1 0 ")); // Distinguish water from a dry-land height fault.
}
void executionTests() {
    Unit bot; MotionMaster motion{&bot};
    Movement::PointsArray path={{0,0,0},{5,8,0},{20,8,0},{100,0,0}};
    assert(motion.MovePointPath(0,path));
    auto* point=dynamic_cast<PointMovementGenerator<Unit>*>(motion.movement.get()); assert(point);
    assert(point->DoInitialize(&bot) && bot.spline.points.size()==path.size() && !bot.spline.direct);
    // Copy ownership: callers may discard/mutate their route after dispatch.
    path[1]={-100,0,0}; assert(same(bot.spline.points[1],{5,8,0}));
    bot.position={12,8,0}; bot.spline.index=1; point->i_recalculateSpeed=true;
    assert(point->DoUpdate(&bot,100));
    assert(bot.spline.points.size()==3 && same(bot.spline.points.front(),bot.position));
    assert(same(bot.spline.points[1],{20,8,0}) && !bot.spline.direct);
    int const launches=bot.spline.launches;
    bot.state|=UNIT_STATE_ROOT; point->i_recalculateSpeed=true;
    assert(point->DoUpdate(&bot,100) && bot.spline.launches==launches);
    bot.state&=~UNIT_STATE_ROOT; bot.state|=UNIT_STATE_STUNNED;
    assert(point->DoUpdate(&bot,100) && bot.spline.launches==launches);
    assert(!point->DoUpdate(nullptr,100));
    assert(!motion.MovePointPath(0,{}) && motion.mutations==1);
    assert(!motion.MovePointPath(0,{{0,0,0},{std::numeric_limits<float>::quiet_NaN(),0,0}}));
    // Existing ordinary point movement remains unchanged.
    Unit ordinary; PointMovementGenerator<Unit> original(0,10,0,0,true);
    assert(original.DoInitialize(&ordinary) && ordinary.spline.direct==1);
    original.i_recalculateSpeed=true;
    assert(original.DoUpdate(&ordinary,100) && ordinary.spline.direct==2);
}
void stuckTests() {
    reset(); Unit bot; MotionMaster motion{&bot}; bot.motion=&motion; bot.stopped=false;
    MovementAction action{&bot};
    auto start=[&]() {
        reset(); action.last={}; bot.position={}; bot.state=0; bot.stopped=false;
        bot.spline.finalized=false; bot.spline.points={{0,0,0},{40,0,0}};
        motion.type=POINT_MOTION_TYPE; motion.Clear();
        action.TrackGroundMovement(100,0,0,false,false);
    };
    auto wait=[&](uint32 count) { for (uint32 i=0;i<count;++i) action.CheckStuck(1000); };
    start(); auto& state=action.last.groundMovement;
    assert(same(state.goal,{100,0,0}) && same(state.endpoint,{40,0,0}));
    wait(3); assert(queries.empty());
    // A new command to the same goal must not restart the no-progress clock.
    state.owner=std::make_shared<int>(1);
    action.TrackGroundMovement(100,0,0,false,false);
    assert(!state.owner); // But it must revoke the previous caller's lease.
    auto owner=std::make_shared<int>(2); state.owner=owner;
    int const clearsBeforeRecovery=motion.cleared;
    replies={Route{},Route{},Route{}}; wait(1);
    assert(state.attempts==1 && state.recovering && queries.size()==3);
    assert(state.owner==owner); // Watchdog recovery retains the issued command's owner.
    assert(motion.cleared==clearsBeforeRecovery); // Replace only the active slot.
    assert(same(queries.back().to,{100,0,0}) && queries[1].to.y==-24);
    assert(hasLog("warn","stuck-detected") && hasLog("info","stuck-recovery-started"));
    assert(same(action.last.destination,{100,0,0}));
    bot.position={3,0,0}; wait(1);
    assert(!state.recovering && hasLog("info","stuck-progress-restored"));
    bot.position={100,0,0}; wait(1);
    assert(!state.active && hasLog("info","stuck-goal-reached"));

    // Forced-control states and casts reset, rather than accumulate, idle time.
    for (int flag : {UNIT_STATE_ROOT,UNIT_STATE_STUNNED,UNIT_STATE_LOST_CONTROL}) {
        start(); wait(3); bot.state=flag; wait(20); bot.state=0; wait(3);
        assert(queries.empty() && state.active);
    }
    start(); wait(3); bot.casting=true; wait(20); bot.casting=false; wait(3);
    assert(queries.empty());
    start(); bot.sitting=true; wait(20); bot.sitting=false; assert(queries.empty());
    start(); bot.speed=0; wait(20); bot.speed=7; assert(queries.empty());
    // Slow but real motion is not stuck; neither is time lost to a server stall.
    start(); bot.speed=0.1f;
    for (int i=0;i<30;++i) { bot.position.x+=0.1f; wait(1); }
    assert(queries.empty()); bot.speed=7;
    start(); action.CheckStuck(60000); assert(state.idleMs==1000 && queries.empty());

    // Intentional stops and completed partial routes must not restart themselves.
    start(); bot.stopped=true; wait(20); assert(!state.active && queries.empty());
    start(); bot.spline.finalized=true; wait(20); assert(!state.active && queries.empty());
    // Same generator's speed update is allowed; foreign splines/goals are not.
    start(); ++bot.spline.id; wait(1); assert(state.active && state.splineId==bot.spline.id);
    start(); ++bot.spline.id; bot.spline.points.back()={200,0,0}; wait(1); assert(!state.active);
    start(); motion.movement=std::make_unique<MovementGenerator>(); wait(1); assert(!state.active);
    start(); motion.type=CHASE_MOTION_TYPE; wait(1); assert(!state.active);
    start(); ++bot.instance; wait(1); assert(!state.active); --bot.instance;
    start(); ++bot.map; wait(1); assert(!state.active); --bot.map;
    for (bool* excluded : {&bot.transport,&bot.vehicle,&bot.flying,&bot.teleport}) {
        start(); *excluded=true; wait(5); *excluded=false; assert(!state.active && queries.empty());
    }
    start(); bot.alive=false; wait(5); bot.alive=true; assert(!state.active && queries.empty());

    // Three bounded recovery attempts use different waypoint families, then stop.
    start(); replies=std::deque<Route>(9,Route{});
    int const clearsBeforeExhaustion=motion.cleared, expiresBeforeExhaustion=motion.expired;
    wait(4); assert(state.attempts==1);
    wait(4); assert(state.attempts==2);
    wait(4); assert(state.attempts==3);
    assert(queries[1].to.y==-24 && queries[4].to.y==48 && queries[7].to.y==-64);
    wait(4); assert(state.exhausted && !state.active && bot.stopped);
    assert(motion.cleared==clearsBeforeExhaustion && motion.expired==expiresBeforeExhaustion+1);
    assert(hasLog("warn","stuck-recovery-exhausted") && queries.size()==9);
    assert(!action.CanStartGroundMovement(100,0,0));
    assert(action.CanStartGroundMovement(200,0,0));
    bot.position={3,0,0}; assert(action.CanStartGroundMovement(100,0,0) && !state.exhausted);

    // Even failed first legs must not reuse waypoint candidates on later attempts.
    start(); replies=std::deque<Route>(30,bad()); wait(4);
    assert(state.recovering && state.attempts==1 && !state.exhausted);
    wait(8);
    assert(state.exhausted);
    std::vector<G3D::Vector3> waypoints;
    for (auto const& query : queries) {
        if (same(query.to,{100,0,0})) continue; // primary diagnostics
        assert(std::none_of(waypoints.begin(),waypoints.end(),[&](auto const& p){return same(p,query.to);}));
        waypoints.push_back(query.to);
    }

    // Missing mmap never forces the failed direct movement or spins unboundedly.
    start(); Route missing=bad("missing-navmesh"); missing.data=false;
    replies={missing,missing,missing}; wait(12);
    assert(state.exhausted && queries.size()==3 && bot.stopped);
    assert(hasLog("warn","stuck-recovery-no-route"));
    // Recovery cannot reuse a useful-but-already-failed primary partial route.
    start(); config.stuckMaxAttempts=1; config.navigationMaxAttempts=1;
    Route partial; partial.type=PATHFIND_INCOMPLETE;
    replies={partial}; wait(4); assert(state.exhausted && bot.stopped);
    // A genuine goal change resets the old attempt budget.
    action.TrackGroundMovement(200,0,0,false,false);
    assert(!state.exhausted && state.attempts==0 && same(state.goal,{200,0,0}));
    assert(hasLog("debug","ground-movement-started"));
}
void swimObservationTests() {
    reset(); Unit bot; MotionMaster motion{&bot}; bot.motion=&motion;
    MovementAction action{&bot};
    // Even without an active point route, water-mode changes refresh native
    // chase speed exactly once; observation must not replace that movement.
    motion.type=CHASE_MOTION_TYPE;
    motion.movement=std::make_unique<MovementGenerator>();
    auto const* chase=motion.top();
    bot.water=true; action.CheckStuck(1000); action.CheckStuck(1000);
    assert(bot.swimming && motion.speedChanges==1 && motion.top()==chase && !motion.cleared);
    bot.water=false; action.CheckStuck(1000);
    assert(!bot.swimming && motion.speedChanges==2 && motion.top()==chase);

    // Owned swimming splines are tracked (water is no longer an exclusion).
    motion.type=POINT_MOTION_TYPE; bot.stopped=false; bot.water=true;
    bot.spline.points={{0,0,0},{40,0,0}};
    action.TrackGroundMovement(100,0,0,false,false);
    action.CheckStuck(1000);
    assert(action.last.groundMovement.active && bot.lastSpeedMode==MOVE_SWIM);
    action.last.groundMovement.backwards=true; action.CheckStuck(1000);
    assert(bot.lastSpeedMode==MOVE_SWIM_BACK);
    bot.swimSpeed=0; action.CheckStuck(1000);
    assert(action.last.groundMovement.idleMs==0 && queries.empty());
    bot.swimSpeed=0.1f;
    for (int i=0;i<30;++i) { bot.position.x+=0.1f; action.CheckStuck(1000); }
    assert(action.last.groundMovement.active && queries.empty());

    // Switching to a different generator relinquishes tracking without
    // clearing, stopping or replanning the foreign command.
    motion.movement=std::make_unique<MovementGenerator>();
    auto const* foreign=motion.top();
    action.CheckStuck(1000);
    assert(!action.last.groundMovement.active && motion.top()==foreign);
    assert(!motion.cleared && !bot.stopped && queries.empty());
}

int main() {
    connectionTests(); waterAndProjectionTests(); searchTests();
    logTests(); executionTests(); stuckTests(); swimObservationTests();
}
"""

with tempfile.TemporaryDirectory(prefix="loa-navigation-recovery-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run([sys.argv[2], "-x", "c++", "-std=c++20", "-O1", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-", "-o", str(binary)],
                   input=source, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("Navigation alternatives, fallback, point-path execution and runtime stuck recovery passed", flush=True)
