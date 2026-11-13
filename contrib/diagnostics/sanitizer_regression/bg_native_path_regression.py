#!/usr/bin/env python3
"""Run the real NormalizePath body with collision/height doubles under ASan.

The bridge coordinates come from the offline VMAP audit. These doubles test
validation policy; they do not reproduce a live spell or claim its causality.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
text = (root / 'src/server/game/Movement/PathGenerator.cpp').read_text()
begin = text.index('void PathGenerator::NormalizePath()')
end = text.index('{', begin) + 1
depth = 1
while depth:
    depth += (text[end] == '{') - (text[end] == '}')
    end += 1
method = text[begin:end]
init_text = (root / 'src/server/game/Movement/Spline/MoveSplineInit.cpp').read_text()
begin = init_text.index('void MoveSplineInit::MoveTo(const Vector3&')
end = init_text.index('{', begin) + 1
depth = 1
while depth:
    depth += (init_text[end] == '{') - (init_text[end] == '}')
    end += 1
move_to = init_text[begin:end]
source = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <string>
#include <utility>
#include <vector>
#define TC_LOG_DEBUG(...) do {} while (0)
using uint32=std::uint32_t;
using dtPolyRef=unsigned long long;
constexpr dtPolyRef INVALID_POLYREF=0;
constexpr int VERTEX_SIZE=3, NAV_WATER=2, NAV_MAGMA=4, NAV_SLIME=8;
constexpr int TYPEID_PLAYER=4, TYPEID_UNIT=3, SPELL_AURA_WATER_WALK=1, SPELL_AURA_GHOST=2;
constexpr int MAP_ALL_LIQUIDS=15, LIQUID_MAP_NO_WATER=0;
constexpr int PATHFIND_NORMAL=1, PATHFIND_NOPATH=8;
constexpr float INVALID_HEIGHT=-100000;
bool dtStatusFailed(int status) {return status!=0;}
namespace G3D {
struct Vector3 {
    float x=0,y=0,z=0;
    Vector3()=default;
    Vector3(float a,float b,float c):x(a),y(b),z(c) {}
};
}
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
struct LiquidData {float level=0, depth_level=0;};
struct Map {
    bool battleground=true;
    bool liquid=false;
    float liquidLevel=5,depthLevel=0;
    mutable std::vector<std::pair<G3D::Vector3,G3D::Vector3>> rays;
    std::function<bool(G3D::Vector3,G3D::Vector3)> clear=[](auto,auto){return true;};
    bool IsBattlegroundOrArena() const {return battleground;}
    int GetLiquidStatus(uint32,float,float,float,int,LiquidData* data,float) const {
        if(data) {data->level=liquidLevel;data->depth_level=depthLevel;}
        return liquid?1:LIQUID_MAP_NO_WATER;
    }
    bool isInLineOfSight(float x,float y,float z,float tx,float ty,float tz,uint32 phase,VMAP::ModelIgnoreFlags) const {
        assert(phase==7); rays.push_back({{x,y,z},{tx,ty,tz}});
        return clear({x,y,z},{tx,ty,tz});
    }
};
struct Unit {
    G3D::Vector3 start;
    std::vector<G3D::Vector3> route;
    const char* failure=nullptr;
    Map map;
    bool isUnit=true, player=true, flying=false, falling=false, transport=false, vehicle=false, water=false, underwater=false;
    bool swimmer=false,waterWalk=false,ghost=false;
    float minWaterHeight=.1f;
    float height=2.541018f;
    std::function<float(G3D::Vector3)> normalize=[](auto p){return p.z;};
    std::function<float(G3D::Vector3)> support;
    Unit const* ToUnit() const {return isUnit?this:nullptr;}
    int GetTypeId() const {return player?TYPEID_PLAYER:TYPEID_UNIT;}
    Map const* GetMap() const {return &map;}
    bool IsFlying() const {return flying;}
    bool CanFly() const {return flying;}
    bool IsFalling() const {return falling;}
    void* GetTransport() const {return transport?(void*)this:nullptr;}
    void* GetVehicle() const {return vehicle?(void*)this:nullptr;}
    bool IsInWater() const {return water;}
    bool IsUnderWater() const {return underwater;}
    bool CanSwim() const {return swimmer;}
    bool HasAuraType(int type) const {return type==SPELL_AURA_WATER_WALK?waterWalk:ghost;}
    float GetMinHeightInWater() const {return minWaterHeight;}
    float GetCollisionHeight() const {return height;}
    uint32 GetPhaseMask() const {return 7;}
    void UpdateAllowedPositionZ(float x,float y,float& z,float* ground) const {
        z=normalize({x,y,z});*ground=support?support({x,y,z}):z;
    }
};
struct Query {int findNearestPoly(float*,float*,int*,dtPolyRef* ref,float*) {*ref=1;return 0;}};
struct Mesh {int getPolyFlags(dtPolyRef,unsigned short* flags) {*flags=1;return 0;}};
struct PathGenerator {
    Unit const* _source;
    bool _privateQuery=false;
    std::vector<G3D::Vector3> _pathPoints;
    int _filter=0, _type=PATHFIND_NORMAL;
    const char* _failureReason=nullptr;
    G3D::Vector3 start;
    Query query; Mesh mesh;
    Query* _navMeshQuery=&query;
    Mesh* _navMesh=&mesh;
    G3D::Vector3 const& GetStartPosition() const {return start;}
    int GetPathType() const {return _type;}
    char const* GetPathFailureReason() const {return _failureReason?_failureReason:"none";}
    auto const& GetPath() const {return _pathPoints;}
    bool CalculatePath(float,float,float,bool) {
        if(_source->failure) {_failureReason=_source->failure;_type=PATHFIND_NOPATH;return false;}
        start=_source->start;_pathPoints=_source->route;NormalizePath();return true;
    }
    void NormalizePath();
};
'''+method+r'''
namespace Movement {
using Vector3=G3D::Vector3;
struct TransportPathTransform {
    TransportPathTransform(Unit*,bool) {}
    Vector3 operator()(Vector3 p) const {return p;}
};
struct MoveSplineInit {
    Unit* unit;
    struct Args {int path_Idx_offset=0;bool TransformForTransport=false;std::vector<Vector3> path;} args;
    void MovebyPath(std::vector<Vector3> const& p) {args.path=p;}
    void MoveTo(Vector3 const&,bool,bool);
};
'''+move_to+r'''
}
int main() {
    // Legacy smooth path at the audited bridge: the second segment crosses
    // static collision at body height although the navmesh corridor is complete.
    Unit unit;
    G3D::Vector3 a{1136.266724f,1217.066650f,-54.042850f};
    G3D::Vector3 b{1135.296875f,1220.947266f,-51.911015f};
    G3D::Vector3 c{1134.666748f,1218.729736f,-51.218346f};
    unit.map.clear=[&](auto from,auto to) {
        return !(std::fabs(from.x-a.x)<.001f && std::fabs(to.x-b.x)<.001f);
    };
    PathGenerator path{&unit}; path.start=a; path._pathPoints={a,a,b,c};
    path.NormalizePath();
    assert(path._type==PATHFIND_NOPATH && std::string(path._failureReason)=="path-body-obstructed");
    assert(std::fabs(unit.map.rays.back().first.z-(a.z+1.270509f))<.00001f);
    assert(path._pathPoints.size()==3);

    // Projecting a point from below a bridge onto its deck cannot create an
    // unchecked initial segment when MoveSplineInit replaces the first vertex.
    auto reset=[&] {
        unit.map.rays.clear(); path._type=PATHFIND_NORMAL; path._failureReason=nullptr;
        path.start={0,0,0}; path._pathPoints={{0,0,1.3f},{1,0,1.3f},{2,0,1.3f}};
    };
    reset(); unit.map.clear=[](auto p,auto q){return std::fabs(q.z-p.z)<1.f;};
    path.NormalizePath();
    assert(path._type==PATHFIND_NOPATH && std::string(path._failureReason)=="path-start-obstructed");
    reset(); unit.map.clear=[](auto p,auto q){return !(p.z<2.f && q.x==1);};
    path.NormalizePath(); // Connector to point 0 is clear; replacement edge is not.
    assert(path._type==PATHFIND_NOPATH && std::string(path._failureReason)=="path-start-obstructed");

    // Test normalized geometry, not raw voxel height; no movement/height snap
    // is applied to the unit. An unobstructed ordinary path remains valid.
    reset(); unit.map.clear=[](auto,auto){return true;};
    unit.normalize=[](auto p){return p.z+1;};
    path.NormalizePath(); assert(path._type==PATHFIND_NORMAL && !path._failureReason);
    assert(std::fabs(path._pathPoints[0].z-2.3f)<.0001f);
    unit.normalize=[](auto p){return p.z;};

    // Recorded AB splines for GUID39/40/53 contain dry terrain vertices
    // below the height query's origin. Native UpdateAllowedPositionZ leaves
    // z untouched when no ground is found: clear VMAP LOS is insufficient.
    for (auto raw : {G3D::Vector3{870.987915f,834.832703f,-60.492588f},
                     G3D::Vector3{870.826599f,835.759888f,-60.292694f},
                     G3D::Vector3{1151.489014f,824.657715f,-103.191864f}}) {
        for (bool privateQuery : {false,true}) {
            reset(); path._privateQuery=privateQuery;
            path.start=raw; path._pathPoints={raw,raw};
            unit.support=[](auto){return INVALID_HEIGHT-100000;};
            path.NormalizePath();
            assert(path._type==PATHFIND_NOPATH && std::string(path._failureReason)=="invalid-ground-height");
        }
    }
    reset(); unit.support=[](auto){return std::numeric_limits<float>::quiet_NaN();};
    path.NormalizePath(); assert(path._type==PATHFIND_NOPATH);
    // Water and transport/flight/fall motion do not require a dry ground ray.
    unit.support=[](auto){return INVALID_HEIGHT;};
    reset(); unit.map.liquid=true; path.NormalizePath();
    assert(path._type==PATHFIND_NORMAL); unit.map.liquid=false;
    for(bool* skip:{&unit.flying,&unit.falling,&unit.transport,&unit.vehicle}) {
        reset(); *skip=true; path.NormalizePath(); *skip=false;
        assert(path._type==PATHFIND_NORMAL);
    }
    // Shared non-BG/NPC queries retain their existing behavior.
    path._privateQuery=false;
    for(bool* included:{&unit.isUnit,&unit.player,&unit.map.battleground}) {
        reset(); *included=false; path.NormalizePath(); *included=true;
        assert(path._type==PATHFIND_NORMAL);
    }
    unit.support={};

    // A support failure retains the last supported point and the first bad
    // point for bounded detour planning, never the unvalidated tail. The path
    // itself must remain forbidden, including when point zero has no support.
    for (unsigned failed : {0u, 1u, 2u}) {
        reset(); path._privateQuery=true;
        path._pathPoints={{0,0,0},{1,0,0},{2,0,0},{3,0,0}};
        unit.support=[failed](auto p) {return p.x==float(failed)?INVALID_HEIGHT:p.z;};
        path.NormalizePath();
        assert(path._type==PATHFIND_NOPATH && std::string(path._failureReason)=="invalid-ground-height");
        assert(path._pathPoints.size()==failed+1 && path._pathPoints.back().x==float(failed));
    }
    unit.support={}; path._privateQuery=false;

    // The shared-query extension is limited to BG players on ordinary ground.
    unit.map.clear=[](auto,auto){return false;};
    for(bool* skip:{&unit.flying,&unit.falling,&unit.transport,&unit.vehicle,&unit.water,&unit.underwater}) {
        reset(); *skip=true; path.NormalizePath(); *skip=false;
        assert(path._type==PATHFIND_NORMAL && unit.map.rays.empty());
    }
    for(bool* included:{&unit.isUnit,&unit.player,&unit.map.battleground}) {
        reset(); *included=false; path.NormalizePath(); *included=true;
        assert(path._type==PATHFIND_NORMAL && unit.map.rays.empty());
    }
    reset(); path._pathPoints.clear(); path.NormalizePath(); assert(unit.map.rays.empty());
    // Existing private bot queries retain their collision policy outside BGs.
    reset(); path._privateQuery=true; unit.map.battleground=false;
    path.NormalizePath(); assert(path._type==PATHFIND_NOPATH);
    // Exercise the actual spline entry point: a veto must not fall through to
    // the historical direct fallback, including when reusing an initializer.
    unit.map.battleground=true; unit.route={a,b,c}; unit.start=a;
    Movement::MoveSplineInit init{&unit};
    init.args.path={{9,9,9},{10,10,10}};
    init.MoveTo(c,true,false);
    assert(init.args.path.empty());
    for(auto reason:{"path-body-obstructed","path-start-obstructed","invalid-ground-height"}) {
        unit.failure=reason; init.args.path={{9,9,9}};
        init.MoveTo(c,true,false); assert(init.args.path.empty());
    }
    unit.failure=nullptr; unit.map.clear=[](auto,auto){return true;};
    init.MoveTo(c,true,false); assert(init.args.path.size()==3);
    unit.failure="missing-navmesh";
    init.MoveTo(c,true,false); assert(init.args.path.size()==2 && init.args.path.back().x==c.x);
    unit.failure="path-body-obstructed";
    init.MoveTo(c,false,false); assert(init.args.path.size()==2); // Explicit non-path motion.

    // Native GUID39 Charge spline93300 starts in water but ends at the water
    // plane without a water-walk aura. Use the logged geometry and controlled
    // support/liquid data with the actual NormalizePath, not a copied policy.
    Unit swimmer; PathGenerator wet{&swimmer};
    auto resetWater=[&] {
        swimmer=Unit{}; swimmer.swimmer=true; swimmer.water=true;
        swimmer.map.liquid=true; swimmer.map.liquidLevel=-66.889992f;
        swimmer.map.depthLevel=-79.791824f; swimmer.minWaterHeight=1.203f;
        swimmer.support=[&](auto){return swimmer.map.depthLevel;};
        wet._privateQuery=false; wet._type=PATHFIND_NORMAL; wet._failureReason=nullptr;
        wet.start={1088.201416f,1090.506470f,-68.092987f};
        wet._pathPoints={wet.start,{1082.f,1086.f,-66.889992f},{1078.465820f,1083.517944f,-66.889992f}};
    };
    for(bool privateQuery:{false,true}) for(bool inWater:{false,true}) {
        resetWater(); wet._privateQuery=privateQuery; swimmer.water=inWater;
        wet.NormalizePath(); assert(wet._type==PATHFIND_NORMAL);
        for(auto p:wet._pathPoints) assert(p.z<swimmer.map.liquidLevel-.1f);
        assert(!swimmer.map.rays.empty()); // Changed underwater points must pass body LOS.
    }
    // Real water-walk permission, ghost movement and unrelated locomotion stay
    // outside immersion. Shared NPC/outside-BG behavior is not expanded.
    for(bool* skip:{&swimmer.waterWalk,&swimmer.ghost,&swimmer.flying,&swimmer.falling,
                   &swimmer.transport,&swimmer.vehicle}) {
        resetWater(); *skip=true; wet.NormalizePath();
        assert(wet._pathPoints.back().z==swimmer.map.liquidLevel);
    }
    for(bool* included:{&swimmer.player,&swimmer.isUnit,&swimmer.swimmer,&swimmer.map.battleground,&swimmer.map.liquid}) {
        resetWater(); *included=false; wet.NormalizePath();
        assert(wet._pathPoints.back().z==-66.889992f);
    }
    resetWater(); wet._privateQuery=true; swimmer.map.battleground=false;
    wet.NormalizePath(); assert(wet._pathPoints.back().z<swimmer.map.liquidLevel-.1f);
    // A VMAP rock just below the surface is higher than the ADT liquid bottom.
    // Immersion may not push the bot underneath that actual support.
    resetWater(); float rock=swimmer.map.liquidLevel-.05f;
    swimmer.support=[&](auto){return rock;}; wet.NormalizePath();
    assert(std::fabs(wet._pathPoints.back().z-rock)<.00001f);
    resetWater(); swimmer.map.clear=[](auto,auto to){return to.x>1080.f;};
    wet.NormalizePath(); assert(wet._type==PATHFIND_NOPATH);
    assert(std::string(wet._failureReason)=="path-body-obstructed");
}
'''
env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-native-path-') as tmp:
    binary=str(Path(tmp)/'test')
    def run(code):
        subprocess.run([sys.argv[2],'-std=c++20','-O1','-g','-no-pie','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-x','c++','-','-o',binary],input=code,text=True,check=True)
        return subprocess.run([binary],env=env,capture_output=True,text=True)
    result=run(source)
    assert result.returncode==0,result.stderr
    print('Native BG path normalization: passed under ASan/UBSan')
    for label,old,new in (
        ('shared-query validation', '(_privateQuery || battlegroundGroundPlayer || normalizeSwimmingPath)', '(_privateQuery)'),
        ('shared swimmer immersion', '(_privateQuery || battlegroundPlayer)', '(_privateQuery)'),
        ('water-walk permission', '!unit->HasAuraType(SPELL_AURA_WATER_WALK)', 'true'),
        ('ghost permission', '!unit->HasAuraType(SPELL_AURA_GHOST)', 'true'),
        ('water support', 'std::max(std::max(groundZ, liquid.depth_level),', 'std::max(liquid.depth_level,'),
        ('actual first segment', 'std::min<size_t>(2, _pathPoints.size())', 'std::min<size_t>(1, _pathPoints.size())'),
        ('collision direct fallback', 'args.path.clear();', 'args.path.resize(2);'),
        ('missing ground accepted', '(!std::isfinite(groundZ) || groundZ <= INVALID_HEIGHT)', 'false'),
        ('lost support failure location',
         '// This prefix is still NOPATH: its collision pass has not run.\n            _pathPoints.resize(i + 1);',
         '// Mutation: retain an unvalidated tail after missing support.'),
        ('invalid-ground direct fallback', ' || reason == "invalid-ground-height"', ''),
    ):
        assert old in source
        result=run(source.replace(old,new))
        assert result.returncode!=0, 'Mutation was not rejected: '+label
        print('Mutation rejected:',label)
