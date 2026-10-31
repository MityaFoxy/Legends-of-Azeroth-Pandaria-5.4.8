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
#include <string>
#include <utility>
#include <vector>
using uint32=std::uint32_t;
using dtPolyRef=unsigned long long;
constexpr dtPolyRef INVALID_POLYREF=0;
constexpr int VERTEX_SIZE=3, NAV_WATER=2, NAV_MAGMA=4, NAV_SLIME=8;
constexpr int TYPEID_PLAYER=4, TYPEID_UNIT=3, SPELL_AURA_WATER_WALK=1;
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
    mutable std::vector<std::pair<G3D::Vector3,G3D::Vector3>> rays;
    std::function<bool(G3D::Vector3,G3D::Vector3)> clear=[](auto,auto){return true;};
    bool IsBattlegroundOrArena() const {return battleground;}
    int GetLiquidStatus(uint32,float,float,float,int,LiquidData*,float) const {return LIQUID_MAP_NO_WATER;}
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
    float height=2.541018f;
    std::function<float(G3D::Vector3)> normalize=[](auto p){return p.z;};
    Unit const* ToUnit() const {return isUnit?this:nullptr;}
    int GetTypeId() const {return player?TYPEID_PLAYER:TYPEID_UNIT;}
    Map const* GetMap() const {return &map;}
    bool IsFlying() const {return flying;}
    bool IsFalling() const {return falling;}
    void* GetTransport() const {return transport?(void*)this:nullptr;}
    void* GetVehicle() const {return vehicle?(void*)this:nullptr;}
    bool IsInWater() const {return water;}
    bool IsUnderWater() const {return underwater;}
    bool CanSwim() const {return false;}
    bool HasAuraType(int) const {return false;}
    float GetMinHeightInWater() const {return .1f;}
    float GetCollisionHeight() const {return height;}
    uint32 GetPhaseMask() const {return 7;}
    void UpdateAllowedPositionZ(float x,float y,float& z,float* ground) const {z=normalize({x,y,z});*ground=z;}
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
    for(auto reason:{"path-body-obstructed","path-start-obstructed"}) {
        unit.failure=reason; init.args.path={{9,9,9}};
        init.MoveTo(c,true,false); assert(init.args.path.empty());
    }
    unit.failure=nullptr; unit.map.clear=[](auto,auto){return true;};
    init.MoveTo(c,true,false); assert(init.args.path.size()==3);
    unit.failure="missing-navmesh";
    init.MoveTo(c,true,false); assert(init.args.path.size()==2 && init.args.path.back().x==c.x);
    unit.failure="path-body-obstructed";
    init.MoveTo(c,false,false); assert(init.args.path.size()==2); // Explicit non-path motion.
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
        ('shared-query validation', '(_privateQuery || battlegroundGroundPlayer)', '(_privateQuery)'),
        ('actual first segment', 'std::min<size_t>(2, _pathPoints.size())', 'std::min<size_t>(1, _pathPoints.size())'),
        ('collision direct fallback', 'args.path.clear();', 'args.path.resize(2);'),
    ):
        assert old in source
        result=run(source.replace(old,new))
        assert result.returncode!=0, 'Mutation was not rejected: '+label
        print('Mutation rejected:',label)
