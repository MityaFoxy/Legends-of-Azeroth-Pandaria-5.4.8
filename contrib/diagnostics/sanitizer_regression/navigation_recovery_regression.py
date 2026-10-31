#!/usr/bin/env python3
"""Exercise actual route selection, logging and point-path execution with doubles.

The scripted queries test policy, not real mmap topology or client movement.
Water/ground connector bodies are real; terrain, liquids and LOS are doubles.
Use --verify-mutations to verify rejection of disabled safety/recovery guards.
"""
import os
import pathlib
import re
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
#include <functional>
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
constexpr int UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2, UNIT_STATE_ROAMING=4, UNIT_STATE_ROAMING_MOVE=8, UNIT_STATE_CHARGING=16;
constexpr int UNIT_STATE_LOST_CONTROL=UNIT_STATE_CHARGING|32;
constexpr int TYPEID_UNIT=0, TYPEID_PLAYER=1, EVENT_CHARGE_PREPATH=99;
constexpr int POINT_MOTION_TYPE=1, CHASE_MOTION_TYPE=2, MOVE_RUN=0, MOVE_RUN_BACK=1, MOVEMENTFLAG_SWIMMING=8;
constexpr int MOVE_SWIM=2, MOVE_SWIM_BACK=3;
constexpr int MAP_ALL_LIQUIDS=15, MAP_LIQUID_STATUS_IN_CONTACT=14;
constexpr int LIQUID_MAP_NO_WATER=0, LIQUID_MAP_UNDER_WATER=8;
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
struct LiquidData { float level=0, depth_level=0; };
using MovementSlot = int;
constexpr MovementSlot MOTION_SLOT_ACTIVE=1;
constexpr MovementSlot MOTION_SLOT_CONTROLLED=2;
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
namespace Movement { using PointsArray=std::vector<G3D::Vector3>; struct SplineBase { enum { ModeLinear=0 }; }; }
namespace Trinity {
bool IsValidMapCoord(float x,float y,float z) { return std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z); }
}
struct Creature;
struct Formation { Creature* GetLeader() const { return nullptr; } void LeaderStartedMoving() {} };
struct Creature { Formation* GetFormation() const { return nullptr; } };
struct Guid {
    uint32 counter=7;
    uint32 GetCounter() const { return counter; }
    std::uint64_t GetRawValue() const { return counter; }
};
struct Aura {
    uint32 id=123, caster=155;
    int32 duration=2400;
    uint32 GetId() const { return id; }
    int32 GetDuration() const { return duration; }
    Guid GetCasterGUID() const { return {caster}; }
};
struct AuraApplication {
    Aura aura;
    uint32 mask=3;
    uint32 GetEffectMask() const { return mask; }
    Aura const* GetBase() const { return &aura; }
};
struct Map {
    mutable std::vector<std::pair<G3D::Vector3,G3D::Vector3>> rays;
    bool collision=true, liquid=false, los=true;
    float liquidLevel=2, liquidBottom=-2, dryAt=std::numeric_limits<float>::infinity();
    mutable int liquidSamples=0, losChecks=0;
    int GetLiquidStatus(uint32,float x,float,float,int,LiquidData* data,float) const {
        ++liquidSamples;
        if (!liquid || std::fabs(x-dryAt)<0.1f) return LIQUID_MAP_NO_WATER;
        if (data) { data->level=liquidLevel; data->depth_level=liquidBottom; }
        return MAP_LIQUID_STATUS_IN_CONTACT;
    }
    bool isInLineOfSight(float x,float y,float z,float tx,float ty,float tz,uint32,VMAP::ModelIgnoreFlags) const {
        rays.push_back({{x,y,z},{tx,ty,tz}});
        ++losChecks; return los;
    }
    bool CheckCollisionAndGetValidCoords(void const*,float,float,float,float& x,float& y,float& z,bool=true) const {
        (void)x;(void)y;(void)z; return collision;
    }
};
struct Spline {
    int firstIndex=0, lastIndex=-1, splineMode=0;
    bool cyclic=false, onTransport=false;
    Spline const& _Spline() const { return *this; }
    auto const& getPoints() const { return points; }
    int first() const { return firstIndex; }
    int last() const { return lastIndex<0 ? int(points.size())-1 : lastIndex; }
    int mode() const { return splineMode; }
    bool isCyclic() const { return cyclic; }
    bool Initialized() const { return points.size()>=2; }
    int _currentSplineIdx() const { return index; }
    int index=0, launches=0, direct=0;
    bool finalized=false;
    bool falling=false;
    Movement::PointsArray points;
    int currentPathIdx() const { return index; }
    bool Finalized() const { return finalized; }
    bool isFalling() const { return falling; }
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
    uint32 guidValue=7;
    bool combat=false;
    Unit* victim=nullptr;
    std::vector<std::pair<uint32,AuraApplication*>> appliedAuras;
    mutable int auraReads=0;
    auto const& GetAppliedAuras() const { ++auraReads; return appliedAuras; }
    bool IsInCombat() const { return combat; }
    Unit const* GetVictim() const { return victim; }
    bool flying=false,water=false,vehicle=false,teleport=false,alive=true,casting=false,sitting=false;
    bool swimFlag=false,canSwim=true;
    float speed=7;
    float ground=0, groundHoleAt=std::numeric_limits<float>::infinity();
    float bridgeSurface=std::numeric_limits<float>::quiet_NaN();
    bool missingLeftGround=false;
    mutable int lastSpeedType=-1, heightSamples=0;
    Map mapObject;
    MotionMaster* motion=nullptr;
    Spline spline;
    Spline* movespline=&spline;
    float GetPositionX() const { return position.x; }
    float GetPositionY() const { return position.y; }
    float GetPositionZ() const { return position.z; }
    uint32 GetMapId() const { return map; }
    uint32 GetInstanceId() const { return instance; }
    Guid GetGUID() const { return {guidValue}; }
    Map* GetMap() { return &mapObject; }
    uint32 GetPhaseMask() const { return 1; }
    float GetCollisionHeight() const { return 2; }
    void* GetTransport() const { return transport ? (void*)this : nullptr; }
    float GetMapHeight(float x,float y,float z,bool=true,float search=50) const {
        ++heightSamples;
        // WorldObject adds its height-search offset before casting down. A
        // finite VMAP ray can miss a bridge and expose the lower raw terrain.
        float origin=z+HEIGHT_SEARCH_OFFSET;
        if (std::isfinite(bridgeSurface) && origin>=bridgeSurface && origin-bridgeSurface<=search)
            return bridgeSurface;
        return invalidHeight || (missingLeftGround && y>0) || std::fabs(x-groundHoleAt)<0.1f ? INVALID_HEIGHT : ground;
    }
    bool IsStopped() const { return stopped; }
    void StopMoving() { stopped=true; }
    MotionMaster* GetMotionMaster() const;
    uint32 movementFlags=0;
    bool falling=false;
    uint32 GetUnitMovementFlags() const { return movementFlags; }
    bool IsFalling() const { return falling; }
    void* GetVehicle() const { return vehicle ? (void*)this : nullptr; }
    bool IsFlying() const { return flying; }
    bool IsInWater() const { return water; }
    bool IsUnderWater() const { return water; }
    bool HasUnitMovementFlag(int flag) const { assert(flag==MOVEMENTFLAG_SWIMMING); return swimFlag; }
    bool CanSwim() const { return canSwim; }
    bool SetSwim(bool value) { bool changed=swimFlag!=value; swimFlag=value; return changed; }
    bool IsBeingTeleported() const { return teleport; }
    bool IsAlive() const { return alive; }
    bool IsNonMeleeSpellCasted(bool) const { return casting; }
    bool IsSitState() const { return sitting; }
    float GetSpeed(int type) const { lastSpeedType=type; return speed; }
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
    int type=POINT_MOTION_TYPE,cleared=0;
    int speedChanges=0;
    void PropagateSpeedChange() { ++speedChanges; }
    MovementGenerator* top() const { return movement.get(); }
    int GetCurrentMovementGeneratorType() const { return type; }
    int GetMotionSlotType(int slot) const { assert(slot==MOTION_SLOT_CONTROLLED); return 0; }
    void Clear() { ++cleared; movement.reset(); }
    void Mutate(MovementGenerator* m,MovementSlot) { ++mutations; movement.reset(m); }
    bool MovePointPath(uint32,Movement::PointsArray const&,MovementSlot=MOTION_SLOT_ACTIVE);
};
MotionMaster* Unit::GetMotionMaster() const {
    static MotionMaster idle{nullptr};
    return motion?motion:&idle;
}
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
    std::string getName() const { return "fixture movement"; }
    Movement::PointsArray SearchForBestPath(float,float,float,bool&,bool=false,uint32=0);
    void LogNavigationResult(char const*,char const*,uint32,uint32,float,float,float,bool,NavigationDiagnostics const* =nullptr);
    bool CanStartGroundMovement(float,float,float);
    void TrackGroundMovement(float,float,float,bool,bool);
    void LogStuckResult(char const*,uint32,bool=true);
    void CheckStuck(uint32);
    bool ValidateWaterConnection(G3D::Vector3 const&,G3D::Vector3 const&);
    bool ValidateGroundConnection(G3D::Vector3 const&,G3D::Vector3 const&);
    bool IsMovingAllowed() const { return true; } // state-only root/stun have no aura guard
};
#define AI_VALUE(type,name) this->last
struct Row { std::string level,text,formatted; };
std::vector<Row> logs;
template<class... Args> void emit(char const* level,char const*,char const* format,Args... args) {
    std::ostringstream out;
    out << format << ' ';
    ((out << args << ' '),...);
    std::string formatted=format;
    size_t position=0;
    auto substitute=[&](auto const& value) {
        position=formatted.find("{}",position);
        assert(position!=std::string::npos);
        std::ostringstream text; text << value;
        auto replacement=text.str();
        formatted.replace(position,2,replacement);
        position+=replacement.size();
    };
    (substitute(args),...);
    assert(formatted.find("{}",position)==std::string::npos);
    logs.push_back({level,out.str(),formatted});
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
std::function<Route(G3D::Vector3 const&,G3D::Vector3 const&)> routeFor;
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
        if (routeFor) route=routeFor(*from,{x,y,z});
        else { assert(!replies.empty()); route=replies.front(); replies.pop_front(); }
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
void reset() { config={}; replies.clear(); queries.clear(); routeFor={}; logs.clear(); tick=100; }
bool hasLog(char const* level,char const* text) {
    return std::any_of(logs.begin(),logs.end(),[&](Row const& r) {
        return r.level==level && r.text.find(text)!=std::string::npos;
    });
}
int summaries() { return std::count_if(logs.begin(),logs.end(),[](Row const& r){return r.level!="debug";}); }
void connectionTests() {
    Unit bot; MovementAction action{&bot};
    // Execute real connector validators against sampled terrain/liquid/LOS.
    // Captured BG failure: interpolation is 0.55 m above a VMAP surface. The
    // extra caller offset used to miss that surface and return lower terrain.
    bot.ground=-67.51784f; bot.bridgeSurface=-61.788746f;
    assert(action.ValidateGroundConnection({874.3679f,983.1656f,-61.237156f},
        {874.3679f,983.1656f,-61.788746f}));
    // The same layered geometry at arbitrary coordinates/heights, in both
    // directions, works without GUID, map, or logged-coordinate special cases.
    bot.ground=-8; bot.bridgeSurface=0;
    for (float gap:{0.2f,0.49f,0.51f,0.55f,1.5f,1.99f}) {
        assert(action.ValidateGroundConnection({0,0,gap},{0,0,0}));
        assert(action.ValidateGroundConnection({0,0,0},{0,0,gap}));
    }
    assert(!action.ValidateGroundConnection({0,0,2.01f},{0,0,0}));
    bot.mapObject.los=false;
    assert(!action.ValidateGroundConnection({0,0,-0.55f},{0,0,0}));
    bot.mapObject.los=true;
    bot.bridgeSurface=std::numeric_limits<float>::quiet_NaN(); bot.ground=0;
    bot.heightSamples=0;
    assert(action.ValidateGroundConnection({0,0,0},{3,0,0}));
    assert(bot.heightSamples==13); // Quarter-metre sampling, both endpoints.
    assert(!action.ValidateGroundConnection({0,0,0},{3.01f,0,0}));
    bot.mapObject.los=false;
    assert(!action.ValidateGroundConnection({0,0,0},{1.0283356f,0,0}));
    bot.mapObject.los=true; bot.groundHoleAt=0.5f;
    assert(!action.ValidateGroundConnection({0,0,0},{1,0,0}));
    bot.groundHoleAt=std::numeric_limits<float>::infinity();
    bot.invalidHeight=true;
    assert(!action.ValidateGroundConnection({0,0,0},{1,0,0}));
    bot.invalidHeight=false; bot.ground=-2.01f;
    assert(!action.ValidateGroundConnection({0,0,0},{1,0,0}));
    bot.ground=std::numeric_limits<float>::quiet_NaN();
    assert(!action.ValidateGroundConnection({0,0,0},{1,0,0}));
    bot.ground=0;
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    bot.mapObject.liquid=true; bot.mapObject.liquidSamples=0;
    assert(action.ValidateWaterConnection({0,0,0},{16,0,0}));
    assert(bot.mapObject.liquidSamples==33); // Half-metre samples.
    assert(!action.ValidateWaterConnection({0,0,0},{16.01f,0,0}));
    bot.mapObject.dryAt=0.5f;
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    bot.mapObject.dryAt=std::numeric_limits<float>::infinity();
    bot.mapObject.los=false;
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    bot.mapObject.los=true;
    assert(action.ValidateWaterConnection({0,0,-2.04f},{1,0,-2.04f}));
    assert(!action.ValidateWaterConnection({0,0,-2.06f},{1,0,-2.06f}));
    assert(action.ValidateWaterConnection({0,0,2.75f},{1,0,2.75f}));
    assert(!action.ValidateWaterConnection({0,0,2.76f},{1,0,2.76f}));
    bot.mapObject.liquidLevel=std::numeric_limits<float>::quiet_NaN();
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    bot.mapObject.liquidLevel=bot.mapObject.liquidBottom;
    assert(!action.ValidateWaterConnection({0,0,0},{1,0,0}));
    // Water can support a short shoreline connector over deep terrain.
    bot.mapObject.liquidLevel=2; bot.ground=-10;
    assert(action.ValidateGroundConnection({0,0,0},{1,0,0}));
    bot.mapObject.liquid=false;
    assert(!action.ValidateGroundConnection({0,0,0},{1,0,0}));
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
void continuationTests() {
    reset(); Unit bot; MovementAction action{&bot}; bool navigation=false;
    // The old blanket >1 m rejection is now a validated connector, not a
    // widened unconditional tolerance. Obstructions must still reject it.
    for (float offset : {0.05f,1.0283356f,2.f,3.f,3.01f}) {
        reset(); action.last={}; config.navigationMaxAttempts=1;
        Route projected; projected.automatic=false;
        projected.points={{offset,0,0},{100,0,0}}; replies={projected};
        auto path=action.SearchForBestPath(100,0,0,navigation,true);
        if (offset<=3.f) {
            assert(navigation && !path.empty() && same(path.back(),{100,0,0}));
            assert(path.size()==(offset>0.1f ? 3u : 2u));
            if (offset>0.1f) assert(same(path.front(),bot.position));
        } else assert(path.empty() && hasLog("warn","path-start-mismatch"));
    }
    reset(); action.last={}; config.navigationMaxAttempts=1; bot.mapObject.los=false;
    Route blocked; blocked.automatic=false; blocked.points={{1.0283356f,0,0},{100,0,0}};
    replies={blocked};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty() && navigation);
    bot.mapObject.los=true;

    // A short unobstructed underwater route needs no Detour query. A dry gap
    // forbids this shortcut even when both endpoints lie inside water.
    reset(); action.last={}; bot.water=true; bot.mapObject.liquid=true;
    auto path=action.SearchForBestPath(10,0,0,navigation,true);
    assert(queries.empty() && navigation && path.size()==2 && same(path.back(),{10,0,0}));
    bot.mapObject.dryAt=5; replies=std::deque<Route>(5,bad());
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    assert(!queries.empty());
    bot.water=false; bot.mapObject=Map{};

    // Unsafe surface normalization retries with land preference, inside the
    // SAME total query budget; regular travel retains actual swim speed.
    reset(); action.last={}; replies={bad("unsafe-surface-normalization"),Route{}};
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(!path.empty() && queries.size()==2);
    assert(queries[0].swimSpeed==bot.speed && queries[1].swimSpeed==0.01f);
    assert(queries[0].runSpeed==bot.speed && queries[1].runSpeed==bot.speed);
    reset(); action.last={}; config.navigationMaxAttempts=1;
    replies={bad("unsafe-surface-normalization")};
    assert(action.SearchForBestPath(100,0,0,navigation,true).empty() && queries.size()==1);

    // A 200-point prefix retains 8 m for the next replan, without synthesizing
    // a line to the goal. Its saved geometry permits a checked retreat later.
    reset(); action.last={}; Route shortPath; shortPath.type=PATHFIND_SHORT;
    shortPath.automatic=false;
    for (int i=0;i<200;++i) shortPath.points.push_back({float(i),0,0});
    replies={shortPath}; path=action.SearchForBestPath(300,0,0,navigation,true);
    assert(navigation && queries.size()==1 && path.size()==192 && same(path.back(),{191,0,0}));
    assert(action.last.navigationDetour.continuation.size()==path.size());
    bot.position=path.back(); queries.clear();
    tick+=30001; // Allow the next INFO summary without expiring the 60 s history.
    Route wrongLayer; wrongLayer.automatic=false; wrongLayer.points={{197,0,0},{300,0,0}};
    replies={wrongLayer,Route{}};
    path=action.SearchForBestPath(300,0,0,navigation,true);
    assert(navigation && queries.size()==2 && same(queries[1].from,{187,0,0}));
    assert(same(path.front(),{191,0,0}) && same(path[1],{190,0,0}) && same(path.back(),{300,0,0}));
    assert(action.last.navigationDetour.continuation.empty());
    assert(hasLog("info","continuation-retreat-route"));
    bot.position={};

    // Planning failures must rotate alternatives even before any spline runs.
    // Map, instance, goal or idle changes must discard that old history.
    for (int change : {0,1,2,3}) {
        reset(); action.last={}; replies=std::deque<Route>(5,bad());
        assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
        auto first=queries[1].to;
        queries.clear(); replies=std::deque<Route>(5,bad());
        assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
        assert(!same(first,queries[1].to));
        if (change==0) ++bot.map;
        if (change==1) ++bot.instance;
        if (change==2) action.last.navigationDetour.goal={200,0,0};
        if (change==3) tick+=60001;
        queries.clear(); replies=std::deque<Route>(5,bad());
        assert(action.SearchForBestPath(100,0,0,navigation,true).empty());
        assert(same(first,queries[1].to));
    }
}
void obstructionSearchTests() {
    // The narrow first-leg corridors cross a long fence. A wider first leg
    // and its continuation are navigable. Missing ground on the left must
    // not prevent trying the right within the same five-query budget.
    reset(); Unit bot; bot.missingLeftGround=true;
    MovementAction action{&bot}; bool navigation=true;
    routeFor=[](G3D::Vector3 const& from,G3D::Vector3 const& to) {
        if (from.y<=-24 || to.y<=-24) return Route{};
        Route r=bad("path-body-obstructed"); r.automatic=false;
        r.points={from,{19,0,1.5f},{20,0,0}};
        return r;
    };
    auto path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(navigation && queries.size()==5 && path.size()==3);
    assert(path[1].y<=-24 && same(path.back(),{100,0,0}));
    assert(same(queries.back().from,path[1]));
    assert(hasLog("info","alternative-route"));

    // A second fence may still block continuation. Retain only the verified
    // wider first leg, so the next search starts on the other side of this one.
    reset(); action.last={};
    routeFor=[](G3D::Vector3 const& from,G3D::Vector3 const& to) {
        if (from.y==0 && to.y<=-24) return Route{};
        Route r=bad("path-body-obstructed"); r.automatic=false;
        r.points={from,{19,0,1.5f},{20,0,0}};
        return r;
    };
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(navigation && queries.size()==5 && path.size()==2);
    assert(path.back().y<=-24 && !same(path.back(),{100,0,0}));
    assert(hasLog("info","validated-obstacle-bypass"));

    // The finite set of height checks stays bounded even if every candidate
    // is invalid. No bogus path queries or direct movement may be generated.
    reset(); action.last={}; bot.invalidHeight=true; bot.heightSamples=0;
    Route blocked=bad("path-body-obstructed"); blocked.automatic=false;
    blocked.points={{0,0,0},{20,0,0}}; replies={blocked};
    path=action.SearchForBestPath(100,0,0,navigation,true);
    assert(path.empty() && navigation && queries.size()==1 && bot.heightSamples==32);

    // More candidates must not increase the configured expensive query limit.
    for (uint32 budget : {1u,5u,7u,10u}) {
        reset(); action.last={}; bot.invalidHeight=false; bot.missingLeftGround=false;
        config.navigationMaxAttempts=budget;
        replies=std::deque<Route>(budget,blocked);
        path=action.SearchForBestPath(100,0,0,navigation,true);
        assert(path.empty() && navigation && queries.size()==budget);
    }
}
void endpointObstructionTests() {
    // Exact starts/goals/blocked endpoints from the three remaining AB refusals.
    // Path responses are scripted: this tests planner policy, not live geometry.
    struct Case { G3D::Vector3 start,goal,blocked; };
    Case cases[]={
        {{843.5866f,878.2756f,-58.36555f},{813.5677f,874.77924f,-58.034657f},{813.5677f,874.77924f,-58.57741f}},
        {{1161.8827f,1176.844f,-56.439476f},{1157.5034f,1179.2567f,-55.357456f},{1157.5034f,1179.2567f,-56.21999f}},
        {{1200.262f,1134.7853f,-56.801228f},{1181.9203f,1144.2401f,-56.107136f},{1181.9203f,1144.2401f,-56.363285f}}
    };
    for(auto const& c:cases) for(float offset:{0.f,.05f,1.f}) {
        reset(); config.navigationMaxAttempts=7;
        Unit bot; bot.position=c.start; bot.ground=c.blocked.z;
        MovementAction action{&bot}; bool navigation=true;
        G3D::Vector3 obstacle=c.blocked; obstacle.x+=offset;
        Route blocked=bad("path-body-obstructed"); blocked.automatic=false;
        blocked.points={c.start,obstacle}; replies={blocked,Route{},Route{}};
        auto path=action.SearchForBestPath(c.goal.x,c.goal.y,c.goal.z,navigation,true);
        assert(navigation && queries.size()==3 && path.size()==3 && same(path.back(),c.goal));
        assert(same(queries[2].from,queries[1].to));
        // Only the direction may fall back to start->goal. The ring must
        // stay around the obstacle; nondegenerate directions stay unchanged.
        auto direction=c.goal-(offset<=.1f ? c.start : obstacle);
        float horizontal=std::hypot(direction.x,direction.y);
        auto displacement=queries[1].to-obstacle;
        float forward=(displacement.x*direction.x+displacement.y*direction.y)/horizontal;
        float side=(-displacement.x*direction.y+displacement.y*direction.x)/horizontal;
        assert(std::fabs(forward+2)<.002f && std::fabs(side-8)<.002f);
    }
    for(uint32 budget:{1u,2u,7u,10u}) {
        reset(); config.navigationMaxAttempts=budget;
        Unit bot; MovementAction action{&bot}; bool navigation=true;
        Route blocked=bad("path-body-obstructed"); blocked.automatic=false;
        blocked.points={{0,0,0},{10,0,0}};
        replies=std::deque<Route>(budget,blocked);
        assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
        assert(navigation && queries.size()==budget); // No unchecked fallback.
    }
    // Runtime recovery uses the same direction repair, with its own waypoints.
    reset(); config.navigationMaxAttempts=7;
    Unit bot; MovementAction action{&bot}; bool navigation=true;
    Route blocked=bad("path-body-obstructed"); blocked.automatic=false;
    blocked.points={{0,0,0},{10,0,0}}; replies={blocked,Route{},Route{}};
    auto path=action.SearchForBestPath(10,0,0,navigation,true,1);
    assert(navigation && queries.size()==3 && same(path.back(),{10,0,0}));

    // Purely vertical displacement still has no usable horizontal direction.
    reset(); action.last={}; bot.heightSamples=0; blocked.points={{0,0,0},{0,0,3}}; replies={blocked};
    assert(action.SearchForBestPath(0,0,3,navigation,true).empty());
    assert(navigation && queries.size()==1 && bot.heightSamples==0);
}
void diagnosticTests() {
    // Reproduce the run's reason=none: valid projected legs miss their waypoint.
    reset(); config.navigationMaxAttempts=7;
    Unit bot; MovementAction action{&bot}; bool navigation=true;
    Route blocked=bad("path-body-obstructed");
    blocked.automatic=false; blocked.points={{0,0,0},{2,0,0},{3,1,0}};
    replies.push_back(blocked);
    Route projected; projected.automatic=false; projected.points={{0,0,0},{1,0,0}};
    for (int i=0;i<6;++i) replies.push_back(projected);
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    assert(navigation && queries.size()==7 && summaries()==1);
    auto row=logs.back().formatted;
    assert(row.find("action='fixture movement'")!=std::string::npos);
    assert(row.find("outcome=rejected reason=waypoint-not-reached")!=std::string::npos);
    assert(row.find("primaryReason=path-body-obstructed primaryType=8")!=std::string::npos);
    assert(row.find("lastStage=alternative-first lastReason=waypoint-not-reached lastType=1")!=std::string::npos);
    assert(row.find("blockedAttempt=1 blockedStage=primary blockedFrom=(2,0,0) blockedTo=(3,1,0)")!=std::string::npos);

    // A successful first leg may consume the budget before the second leg.
    reset(); action.last={}; config.navigationMaxAttempts=2;
    replies={bad(),Route{}};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    assert(queries.size()==2 && navigation);
    assert(logs.back().formatted.find("outcome=rejected reason=query-budget-exhausted")!=std::string::npos);
    assert(logs.back().formatted.find("blockedAttempt=0 blockedStage=none")!=std::string::npos);

    // A land-preferred retry must not erase the first query's failure.
    reset(); action.last={}; config.navigationMaxAttempts=2;
    replies={bad("unsafe-surface-normalization"),bad("path-body-obstructed")};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    row=logs.back().formatted;
    assert(row.find("primaryReason=unsafe-surface-normalization")!=std::string::npos);
    assert(row.find("lastStage=land-retry lastReason=path-body-obstructed")!=std::string::npos);

    // A normal second leg that stops far from the goal is still rejected.
    reset(); action.last={}; config.navigationMaxAttempts=3;
    projected.points={{5,8,0},{6,8,0}};
    replies={bad(),Route{},projected};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    assert(queries.size()==3 && navigation);
    row=logs.back().formatted;
    assert(row.find("reason=alternative-destination-not-reached")!=std::string::npos);
    assert(row.find("lastStage=alternative-second")!=std::string::npos);
    assert(row.find("queryFrom=(5,8,0) queryTo=(10,0,0)")!=std::string::npos);

    // Latest obstruction is labelled with its own attempt and leg; primary
    // reason must survive, and no stale obstruction may leak into another call.
    reset(); action.last={}; config.navigationMaxAttempts=2;
    replies={bad("navigation-query-node-limit"),blocked};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    row=logs.back().formatted;
    assert(row.find("primaryReason=navigation-query-node-limit")!=std::string::npos);
    assert(row.find("blockedAttempt=2 blockedStage=alternative-first")!=std::string::npos);
    tick+=30000; replies={bad(),bad()};
    assert(action.SearchForBestPath(10,0,0,navigation,true).empty());
    assert(logs.back().formatted.find("blockedAttempt=0 blockedStage=none")!=std::string::npos);
}
void startMismatchDiagnosticsTests() {
    reset(); config.navigationMaxAttempts=2;
    Unit bot; MovementAction action{&bot}; bool navigation=false;
    bot.position={927.1432f,1002.073f,-49.914406f}; bot.ground=-54.29065f;
    bot.movementFlags=4096; bot.falling=true; bot.state=UNIT_STATE_CHARGING|UNIT_STATE_ROOT|UNIT_STATE_STUNNED;
    Unit enemy; enemy.guidValue=155; bot.combat=true; bot.victim=&enemy;
    AuraApplication effect,inactive; inactive.mask=0;
    bot.appliedAuras={{123,&effect},{124,&inactive}};
    bot.spline.falling=true; bot.spline.points={bot.position,{930,1000,-54}};
    Route primary; primary.automatic=false;
    primary.points={{bot.position.x,bot.position.y,bot.ground},{926.43085f,1006.68945f,-54.1566f}};
    Route alternative=primary; alternative.points.front().z-=1;
    replies={primary,alternative};
    assert(action.SearchForBestPath(926.43085f,1006.68945f,-54.1566f,navigation,true).empty());
    assert(queries.size()==2 && summaries()==2);
    auto evidence=std::find_if(logs.begin(),logs.end(),[](Row const& row) {
        return row.formatted.find("outcome=start-mismatch-state")!=std::string::npos;
    });
    assert(evidence!=logs.end());
    auto const& row=evidence->formatted;
    assert(row.find("attempt=1 stage=primary")!=std::string::npos);
    assert(row.find("startOffset=4.376")!=std::string::npos);
    assert(row.find("groundValid=1 groundDelta=4.376")!=std::string::npos);
    assert(row.find("movementFlags=4096 falling=1 charging=1")!=std::string::npos);
    assert(row.find("splineFalling=1 splineEnd=(930,1000,-54)")!=std::string::npos);
    assert(row.find("combat=1 victim=155 rooted=1 stunned=1 lostControl=1")!=std::string::npos);
    assert(row.find("auraCount=1 aurasOmitted=0 auras='123:3:2400:155'")!=std::string::npos);
    assert(logs.back().formatted.find("reason=path-start-mismatch")!=std::string::npos);

    // Diagnostic support sampling shares the warning throttle, never queries
    // navigation, and never presents invalid terrain as a real height delta.
    reset(); action.last={}; bot.heightSamples=0; bot.auraReads=0;
    MovementAction::NavigationDiagnostics d;
    d.mismatchAttempt=1; d.mismatchStage="primary";
    d.mismatchFrom=bot.position; d.mismatchStart=primary.points.front();
    action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
    assert(bot.heightSamples==1 && summaries()==2);
    action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
    assert(bot.heightSamples==1 && bot.auraReads==1 && summaries()==2 && action.last.navigationLogSuppressed==1);
    tick+=30000; bot.invalidHeight=true;
    bot.appliedAuras.assign(33,{123,&effect});
    action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
    assert(bot.heightSamples==2 && summaries()==4);
    assert(logs[logs.size()-2].formatted.find("groundValid=0 groundDelta=0")!=std::string::npos);
    auto const& capped=logs[logs.size()-2].formatted;
    assert(capped.find("auraCount=33 aurasOmitted=1")!=std::string::npos);
    assert(std::count(capped.begin()+capped.find("auras='"),capped.end(),':')==32*3);
    tick+=30000;
    action.LogNavigationResult("alternative-route","path-start-mismatch",1,3,0,0,0,false,&d);
    assert(bot.heightSamples==2 && summaries()==5 && queries.empty());
    assert(bot.auraReads==2);
    tick+=30000; bot.appliedAuras.clear(); bot.combat=false; bot.victim=nullptr; bot.state=0;
    action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
    auto const& cleared=logs[logs.size()-2].formatted;
    assert(cleared.find("combat=0 victim=0 rooted=0 stunned=0 lostControl=0")!=std::string::npos);
    assert(cleared.find("auraCount=0 aurasOmitted=0 auras=''")!=std::string::npos);
}
void activeSplineDiagnosticsTests() {
    reset(); Unit bot; MovementAction action{&bot};
    MovementAction::NavigationDiagnostics d; d.mismatchAttempt=1;
    // Padding is logged for reconstruction, but is not a traversed segment.
    bot.spline.points={{-999,0,0},{0,0,0},{2,0,0},{3,0,0},{999,0,0}};
    bot.spline.firstIndex=1; bot.spline.lastIndex=3; bot.spline.index=2;
    bot.position={2.5f,0,0}; bot.stopped=false;
    action.last.groundMovement.active=true;
    action.last.groundMovement.splineId=bot.spline.id;
    auto emit=[&] {
        tick+=30000;
        bot.mapObject.rays.clear();
        action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
        return logs[logs.size()-2].formatted;
    };
    auto row=emit();
    assert(row.find("splineFirst=1 splineLast=3 splineCurrent=2 splinePointCount=5 splinePointsOmitted=0")!=std::string::npos);
    assert(row.find("0:-999.000000,0.000000,0.000000;1:0.000000")!=std::string::npos);
    assert(row.find("splineLosChecked=1 splineBodyHeight=1 splinePhase=1 splineLos='1:1;2:1' currentLinkLos=1")!=std::string::npos);
    assert(bot.mapObject.rays.size()==3);
    assert(same(bot.mapObject.rays[0].first,{0,0,1}));
    assert(same(bot.mapObject.rays[1].second,{3,0,1}));
    assert(same(bot.mapObject.rays[2].first,{2.5f,0,1}));
    action.LogNavigationResult("rejected","path-start-mismatch",1,1,0,0,0,true,&d);
    assert(bot.mapObject.rays.size()==3); // Shared throttle precedes all LOS work.
    bot.mapObject.los=false; row=emit();
    assert(row.find("splineLos='1:0;2:0' currentLinkLos=0")!=std::string::npos);
    for (bool* excluded : {&bot.spline.finalized,&bot.spline.falling,&bot.spline.cyclic,
                           &bot.spline.onTransport,&bot.transport,&bot.vehicle,&bot.flying}) {
        *excluded=true; row=emit(); *excluded=false;
        assert(bot.mapObject.rays.empty());
        assert(row.find("splineLosChecked=0")!=std::string::npos);
        assert(row.find("currentLinkLos=-1")!=std::string::npos);
    }
    bot.spline.splineMode=1; row=emit(); bot.spline.splineMode=0;
    assert(bot.mapObject.rays.empty());
    bot.spline.index=10; row=emit(); bot.spline.index=2;
    assert(bot.mapObject.rays.empty());
    ++action.last.groundMovement.splineId; row=emit();
    assert(bot.mapObject.rays.empty());
    action.last.groundMovement.splineId=bot.spline.id;
    bot.spline.points.resize(257,{7,8,9}); row=emit();
    assert(row.find("splinePointCount=257 splinePointsOmitted=1")!=std::string::npos);
    assert(row.find("256:7.000000")==std::string::npos && bot.mapObject.rays.empty());
    assert(row.size()<64*1024);
    bot.spline.points.clear(); row=emit();
    assert(row.find("splinePointCount=0 splinePointsOmitted=0 splinePoints=''")!=std::string::npos);
    assert(bot.mapObject.rays.empty() && queries.empty());
    assert(bot.spline.launches==0 && !bot.stopped);
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
    action.last={}; bot.water=true; bot.swimFlag=true;
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
    action.TrackGroundMovement(100,0,0,false,false);
    replies={Route{},Route{},Route{}}; wait(1);
    assert(state.attempts==1 && state.recovering && queries.size()==3);
    assert(same(queries.back().to,{100,0,0}) && queries[1].to.y==-24);
    assert(hasLog("warn","stuck-detected") && hasLog("info","stuck-recovery-started"));
    assert(same(action.last.destination,{100,0,0}));
    bot.position={3,0,0}; wait(1);
    assert(!state.recovering && hasLog("info","stuck-progress-restored"));
    bot.position={100,0,0}; wait(1);
    assert(!state.active && hasLog("info","stuck-goal-reached"));

    // Forced-control states and casts reset, rather than accumulate, idle time.
    for (int flag : {UNIT_STATE_ROOT,UNIT_STATE_STUNNED}) {
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

    // Swimming is observed, not excluded. Shore transitions refresh spline
    // speed exactly once, including idle/chase bots without an owned route.
    start(); bot.water=true; bot.swimFlag=false; motion.speedChanges=0;
    wait(3);
    assert(state.active && state.idleMs==3000 && queries.empty());
    assert(bot.swimFlag && motion.speedChanges==1 && bot.lastSpeedType==MOVE_SWIM);
    replies={Route{},Route{},Route{}}; wait(1);
    assert(state.recovering && state.attempts==1 && queries.size()==3);
    bot.position={3,0,0}; wait(1); assert(!state.recovering);
    bot.water=false; wait(1);
    assert(!bot.swimFlag && motion.speedChanges==2 && bot.lastSpeedType==MOVE_RUN);
    start(); state.backwards=true; bot.water=true; wait(1);
    assert(bot.lastSpeedType==MOVE_SWIM_BACK);
    bot.water=false; wait(1); assert(bot.lastSpeedType==MOVE_RUN_BACK);
    start(); state.active=false; motion.type=CHASE_MOTION_TYPE; motion.speedChanges=0;
    bot.water=true; wait(1);
    assert(bot.swimFlag && motion.speedChanges==1 && queries.empty());
    wait(1); assert(motion.speedChanges==1);
    bot.water=false; wait(1); assert(!bot.swimFlag && motion.speedChanges==2);

    // Three bounded recovery attempts use different waypoint families, then stop.
    start(); replies=std::deque<Route>(9,Route{});
    wait(4); assert(state.attempts==1);
    wait(4); assert(state.attempts==2);
    wait(4); assert(state.attempts==3);
    assert(queries[1].to.y==-24 && queries[4].to.y==48 && queries[7].to.y==-64);
    wait(4); assert(state.exhausted && !state.active && bot.stopped);
    assert(hasLog("warn","stuck-recovery-exhausted") && queries.size()==9);
    assert(!action.CanStartGroundMovement(100,0,0));
    assert(action.CanStartGroundMovement(200,0,0));
    bot.position={3,0,0}; assert(action.CanStartGroundMovement(100,0,0) && !state.exhausted);

    // Even failed first legs must not reuse waypoint candidates on later attempts.
    start(); replies=std::deque<Route>(30,bad()); wait(12);
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
int main() { connectionTests(); searchTests(); continuationTests(); obstructionSearchTests(); endpointObstructionTests(); diagnosticTests(); startMismatchDiagnosticsTests(); activeSplineDiagnosticsTests(); logTests(); executionTests(); stuckTests(); }
"""
production_only = "--production-only" in sys.argv[3:]
if production_only:
    # The published server omits the local evidence payload. Retain every
    # routing/recovery test and skip only tests of that omitted payload.
    source = source.replace(",NavigationDiagnostics const* =nullptr", "")
    for name in ("diagnosticTests", "startMismatchDiagnosticsTests", "activeSplineDiagnosticsTests"):
        begin = source.index("void " + name + "()")
        end = source.index("{", begin) + 1
        depth = 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        source = source[:begin] + source[end:]
        source = source.replace(name + "();", "")
else:
    source = source.replace("struct MovementAction {", "struct MovementAction {\n" + method(
        "modules/mod_playerbots/src/strategy/actions/MovementActions.h", "struct NavigationDiagnostics") + ";")
height_defines = (root / "src/server/game/Miscellaneous/SharedDefines.h").read_text()
height_offset = re.search(r"constexpr float Z_OFFSET_FIND_HEIGHT = ([^;]+);", height_defines).group(1)
source = source.replace("HEIGHT_SEARCH_OFFSET", height_offset)

with tempfile.TemporaryDirectory(prefix="loa-navigation-recovery-") as directory:
    environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                       UBSAN_OPTIONS="halt_on_error=1")

    def run(label, code, expected_failure=False):
        binary = pathlib.Path(directory) / label
        subprocess.run([sys.argv[2], "-x", "c++", "-std=c++20", "-O1", "-g",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-", "-o", str(binary)],
                       input=code, text=True, check=True)
        result = subprocess.run([str(binary)], env=environment, text=True, capture_output=True)
        if expected_failure:
            assert result.returncode != 0 and "Assertion" in result.stderr, result.stderr
            print(f"Mutation {label}: rejected by assertion", flush=True)
        elif result.returncode:
            sys.stderr.write(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, [str(binary)])

    run("regression", source)
    if "--verify-mutations" in sys.argv[3:]:
        for label, signature in (
            ("unchecked-water", "bool MovementAction::ValidateWaterConnection("),
            ("unchecked-ground", "bool MovementAction::ValidateGroundConnection(")):
            original = method(action_path, signature)
            unchecked = original[:original.index("{")] + "{ return true; }"
            assert original in source
            run(label, source.replace(original, unchecked, 1), True)
        for label, original, changed in (
            ("double-height-offset", "GetMapHeight(point.x, point.y, point.z, true, 4.0f)",
             "GetMapHeight(point.x, point.y, point.z + 2.0f, true, 4.0f)"),
            ("lost-endpoint-detour", "if (aroundObstruction && horizontal <= 0.1f)", "if (false)"),
            ("narrow-obstruction-ring", "((variant % 8) / 2)", "(variant / 8)"),
            ("height-candidates-spend-budget", "aroundObstruction && !recoveryAttempt ? 32 : limit", "limit"),
            ("lost-waypoint-reason", 'reason = "waypoint-not-reached";', 'reason = "none";'),
            ("lost-obstruction-evidence", "diagnostics.blockedAttempt = attempts;", "diagnostics.blockedAttempt = 0;"),
            ("lost-start-mismatch-evidence", "diagnostics.mismatchAttempt = attempts;", "diagnostics.mismatchAttempt = 0;"),
            ("normal-only-fallback", "if (normalOnly || bot->GetTransport())", "if (bot->GetTransport())"),
            ("lost-overlap", "constexpr float ReplanOverlap = 8.0f;", "constexpr float ReplanOverlap = 0.0f;"),
            ("swimming-excluded", "bot->IsBeingTeleported() || !bot->IsAlive() || mm.top() != state.generator ||",
             "bot->IsInWater() || bot->IsBeingTeleported() || !bot->IsAlive() || mm.top() != state.generator ||")):
            if production_only and label in ("lost-waypoint-reason", "lost-obstruction-evidence", "lost-start-mismatch-evidence"):
                continue
            assert original in source
            run(label, source.replace(original, changed, 1), True)
print("Navigation alternatives, fallback, point-path execution and runtime stuck recovery passed", flush=True)
