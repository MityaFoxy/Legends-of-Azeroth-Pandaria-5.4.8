#!/usr/bin/env python3
"""Read-only offline AB geometry audit using the built core's Detour/VMAP libs.

Extracts actual GridMap height readers from the current source. Does not run
worldserver, regenerate data, snap bots, or change navigation limits. Static
VMAP/terrain, polygon search and extracted core smoothing are not full live PathGenerator validation:
dynamic collision, liquid selection, normalization and spline motion differ.
Requires the Unix Makefiles sanitizer build (common.dir/flags.make).
"""
import argparse
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def body(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--sample", type=float, nargs=3, action="append", default=[],
                        metavar=("X", "Y", "Z"), help="Additional exact position to audit")
    parser.add_argument("--probe-line", type=float, nargs=6, action="append", default=[],
                        help="Probe a hypothetical direct segment X Y Z X Y Z (not a replay of the run)")
    args = parser.parse_args()
    maps = (args.source / "src/server/game/Maps/Map.cpp").read_text()
    paths = (args.source / "src/server/game/Movement/PathGenerator.cpp").read_text()
    ab = (args.source / "src/server/game/Battlegrounds/Zones/BattlegroundAB.h").read_text()
    nodes = re.search(r"const float BG_AB_NodePositions\[[^;]+?=\s*(\{.*?\n\});", ab, re.S).group(1)
    # Preserve the exact runtime coordinates, deduplicate only identical starts.
    points = []
    pattern = re.compile(r"map=529 instance=\d+ from=\(([^)]+)\).*?reason=(far-from-navigation-polygon|path-start-mismatch)")
    with args.log.open(errors="replace") as log:
        for line in log:
            match = pattern.search(line)
            if match:
                xyz = tuple(float(v) for v in match[1].split(","))
                if len(xyz) != 3:
                    raise ValueError("Invalid logged position")
                if xyz not in points:
                    points.append(xyz)
                if len(points) >= 32:
                    break
    points.extend(tuple(p) for p in args.sample)
    source = r'''
#include <vector>
#include <array>
#include <G3D/Plane.h>
#include <G3D/System.h>
#include "VMapManager2.h"
#include "Errors.h"
#include "Log.h"
#include "DetourNavMesh.h"
#include "DetourNavMeshQuery.h"
#include "DetourAlloc.h"
#include "DetourCommon.h"
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <map>
#include <memory>
#include <string>
constexpr float SIZE_OF_GRIDS=533.3333f, INVALID_HEIGHT=-100000.f;
constexpr int MAP_RESOLUTION=128, MAP_HEIGHT_NO_HEIGHT=1, MAP_HEIGHT_AS_INT16=2, MAP_HEIGHT_AS_INT8=4;
constexpr int MAP_HEIGHT_HAS_FLIGHT_BOUNDS=8;
constexpr int MAP_LIQUID_NO_TYPE=1, MAP_LIQUID_NO_HEIGHT=2;
union u_map_magic {char asChar[4]; uint32 asUInt;};
u_map_magic MapHeightMagic = {{'M','H','G','T'}};
u_map_magic MapLiquidMagic = {{'M','L','I','Q'}};
uint16 const holetab_h[4]={0x1111,0x2222,0x4444,0x8888},holetab_v[4]={0x000F,0x00F0,0x0F00,0xF000};
struct map_heightHeader {uint32 fourcc,flags; float gridHeight,gridMaxHeight;};
struct map_liquidHeader {
    uint32 fourcc; uint16 flags,liquidType;
    uint8 offsetX,offsetY,width,height; float liquidLevel;
};
struct GridMap {
    float _gridHeight=INVALID_HEIGHT, _gridIntHeightMultiplier=0;
    float *m_V8=nullptr,*m_V9=nullptr;
    uint16 *m_uint16_V8=nullptr,*m_uint16_V9=nullptr,*_holes=nullptr;
    uint8 *m_uint8_V8=nullptr,*m_uint8_V9=nullptr;
    G3D::Plane* _minHeightPlanes=nullptr;
    uint16 _liquidType=0;
    uint8 _liquidOffX=0,_liquidOffY=0,_liquidWidth=0,_liquidHeight=0;
    uint16* _liquidEntry=nullptr;
    uint8* _liquidFlags=nullptr;
    float* _liquidMap=nullptr;
    float _liquidLevel=INVALID_HEIGHT;
    float (GridMap::*_gridGetHeight)(float,float) const=&GridMap::getHeightFromFlat;
    bool loadHeightData(FILE*,uint32,uint32);
    bool loadHolesData(FILE*,uint32,uint32);
    bool loadLiquidData(FILE*,uint32,uint32);
    bool isHole(int,int) const;
    float getHeightFromFlat(float,float) const;
    float getHeightFromFloat(float,float) const;
    float getHeightFromUint8(float,float) const;
    float getHeightFromUint16(float,float) const;
    float getLiquidLevel(float,float) const;
    ~GridMap() {
        delete[] m_V8; delete[] m_V9; delete[] m_uint16_V8; delete[] m_uint16_V9;
        delete[] m_uint8_V8; delete[] m_uint8_V9; delete[] _holes;
        delete[] _minHeightPlanes;
        delete[] _liquidEntry; delete[] _liquidFlags; delete[] _liquidMap;
    }
    void Load(std::filesystem::path const& path) {
        FILE* in=fopen(path.c_str(),"rb"); assert(in);
        uint32 header[11]; assert(fread(header,sizeof header,1,in)==1);
        assert(header[0]==0x5350414d && header[1]==10);
        assert(header[5] && loadHeightData(in,header[5],header[6]));
        if(header[7] && header[8]) assert(loadLiquidData(in,header[7],header[8]));
        if(header[9] && header[10]) assert(loadHolesData(in,header[9],header[10]));
        fclose(in);
    }
    float Height(float x,float y) {return (this->*_gridGetHeight)(x,y);}
};
'''
    for signature in ("bool GridMap::loadHeightData(", "bool  GridMap::loadHolesData(",
                      "bool GridMap::isHole(", "float GridMap::getHeightFromFlat(",
                      "float GridMap::getHeightFromFloat(", "float GridMap::getHeightFromUint8(",
                      "float GridMap::getHeightFromUint16(", "bool GridMap::loadLiquidData(",
                      "float GridMap::getLiquidLevel("):
        source += body(maps, signature) + "\n"
    source += r'''
// Actual core smoothing bodies, with only world logging supplied by a double.
constexpr int VERTEX_SIZE=3, MAX_PATH_LENGTH=200, MAX_POINT_PATH_LENGTH=200;
constexpr float SMOOTH_PATH_STEP_SIZE=4.f, SMOOTH_PATH_SLOP=.3f;
constexpr dtPolyRef INVALID_POLYREF=0;
struct AuditGuid { unsigned GetCounter() const { return 0; } };
struct AuditSource { AuditGuid GetGUID() const { return {}; } };
struct SmoothProbe {
    dtNavMesh const* _navMesh;
    dtNavMeshQuery const* _navMeshQuery;
    dtQueryFilter _filter;
    AuditSource owner;
    AuditSource const* _source=&owner;
    uint32 FixupCorridor(dtPolyRef*,uint32,uint32,dtPolyRef const*,uint32);
    bool GetSteerTarget(float const*,float const*,float,dtPolyRef const*,uint32,float*,unsigned char&,dtPolyRef&);
    bool InRangeYZX(float const*,float const*,float,float) const;
    dtStatus FindSmoothPath(float const*,float const*,dtPolyRef const*,uint32,float*,int*,uint32);
};
'''
    for signature in ("uint32 PathGenerator::FixupCorridor(", "bool PathGenerator::GetSteerTarget(",
                      "bool PathGenerator::InRangeYZX(", "dtStatus PathGenerator::FindSmoothPath("):
        source += body(paths, signature).replace("PathGenerator::", "SmoothProbe::") + "\n"
    source += "static float const nodes[5][4] = " + nodes + ";\n"
    # Validate literals before embedding user-supplied positions in the fixture.
    if any(not math.isfinite(v) for p in (*points, *args.probe_line) for v in p):
        raise ValueError("Non-finite coordinates")
    source += "static std::vector<std::array<float,6>> const lines = {" + ",".join(
        "{" + ",".join(f"{v:.9e}f" for v in p) + "}" for p in args.probe_line) + "};\n"
    source += r'''
struct TileHeader {uint32 magic,dtVersion,version,size; char liquids,pad[3];};
static_assert(sizeof(TileHeader)==20);
int main(int argc,char** argv) {
    assert(argc==2);
    // The full server uses G3D allocations before any collision-tree teardown.
    // An empty standalone map may free(nullptr) first; prime the built G3D
    // allocator as well, without changing its or the core's compile policy.
    void* warmup=G3D::System::malloc(1); assert(warmup); G3D::System::free(warmup);
    std::filesystem::path data=argv[1];
    VMAP::VMapManager2 vmap;
    auto mesh=dtAllocNavMesh();
    FILE* in=fopen((data/"mmaps/0529.mmap").c_str(),"rb"); assert(in);
    dtNavMeshParams params; assert(fread(&params,sizeof params,1,in)==1); fclose(in);
    assert(dtStatusSucceed(mesh->init(&params)));
    unsigned tiles=0;
    std::map<std::pair<int,int>,std::unique_ptr<GridMap>> grids;
    for(auto const& entry:std::filesystem::directory_iterator(data/"mmaps")) {
        auto name=entry.path().filename().string();
        if(!name.starts_with("0529_") || !name.ends_with(".mmtile")) continue;
        in=fopen(entry.path().c_str(),"rb"); assert(in);
        TileHeader h; assert(fread(&h,sizeof h,1,in)==1);
        assert(h.magic==0x4d4d4150 && h.version==7 && h.dtVersion==DT_NAVMESH_VERSION);
        auto bytes=static_cast<unsigned char*>(dtAlloc(h.size,DT_ALLOC_PERM)); assert(bytes);
        assert(fread(bytes,h.size,1,in)==1); fclose(in);
        assert(dtStatusSucceed(mesh->addTile(bytes,h.size,DT_TILE_FREE_DATA,0,nullptr))); ++tiles;
    }
    // Load the actual terrain and static collision tiles, not synthetic heights.
    for(auto const& entry:std::filesystem::directory_iterator(data/"maps")) {
        int x,y;
        if(sscanf(entry.path().filename().c_str(),"0529_%d_%d.map",&x,&y)!=2) continue;
        auto grid=std::make_unique<GridMap>(); grid->Load(entry.path()); grids[{x,y}]=std::move(grid);
        int status=vmap.loadMap((data/"vmaps").c_str(),529,x,y);
        printf("vmap_tile=%d,%d load_status=%d\n",x,y,status);
        assert(status==VMAP::VMAP_LOAD_RESULT_OK);
    }
    printf("valid_mmap_tiles=%u terrain_tiles=%zu\n",tiles,grids.size());
    auto query=dtAllocNavMeshQuery(); assert(dtStatusSucceed(query->init(mesh,1024)));
    auto resetQuery=[&](int capacity) {
        // Detour init() grows pools but never shrinks them. Each measurement
        // needs a fresh query, especially after a 4096-node smoothing probe.
        dtFreeNavMeshQuery(query); query=dtAllocNavMeshQuery(); assert(query);
        assert(dtStatusSucceed(query->init(mesh,capacity)));
    };
    dtQueryFilter filter; filter.setIncludeFlags(15); filter.setExcludeFlags(0);
    auto nearest=[&](float x,float y,float z,float* closest) {
        float p[3]={y,z,x},ext[3]={3,5,3}; dtPolyRef ref=0;
        assert(dtStatusSucceed(query->findNearestPoly(p,ext,&filter,&ref,closest)));
        if(!ref) {ext[1]=50; assert(dtStatusSucceed(query->findNearestPoly(p,ext,&filter,&ref,closest)));}
        return ref;
    };
    auto sample=[&](int id,float x,float y,float z) {
        float closest[3]={}; dtPolyRef ref=nearest(x,y,z,closest);
        auto g=grids.find({int(32-x/SIZE_OF_GRIDS),int(32-y/SIZE_OF_GRIDS)});
        assert(g!=grids.end()); float terrain=g->second->Height(x,y);
        float collision=vmap.getHeight(529,x,y,z+2.f,50.f);
        float liquid=g->second->getLiquidLevel(x,y);
        dtMeshTile const* tile=nullptr; dtPoly const* poly=nullptr;
        if(ref) assert(dtStatusSucceed(mesh->getTileAndPolyByRef(ref,&tile,&poly)));
        float distance=ref?std::sqrt(std::pow(closest[2]-x,2)+std::pow(closest[0]-y,2)+std::pow(closest[1]-z,2)):-1;
        printf("sample=%d xyz=(%.5f,%.5f,%.5f) terrain_z=%.5f static_vmap_z=%.5f liquid_z=%.5f nearest_z=%.5f poly_flags=%u poly_distance=%.5f ref=%llu\n",
            id,x,y,z,terrain,collision,liquid,ref?closest[1]:INVALID_HEIGHT,poly?poly->flags:0,distance,static_cast<unsigned long long>(ref));
    };
    for(int i=0;i<5;++i) sample(i,nodes[i][0],nodes[i][1],nodes[i][2]);
    float x,y,z; int id=5; while(scanf("%f %f %f",&x,&y,&z)==3) sample(id++,x,y,z);
    for(size_t i=0;i<lines.size();++i) {
        auto const& p=lines[i];
        int steps=std::max(1,int(std::ceil(std::hypot(p[3]-p[0],p[4]-p[1]))));
        int dryBelow=0; float maxDepth=0,worst[3]={};
        for(int step=0;step<=steps;++step) {
            float t=float(step)/steps;
            float x=p[0]+t*(p[3]-p[0]),y=p[1]+t*(p[4]-p[1]),z=p[2]+t*(p[5]-p[2]);
            auto g=grids.find({int(32-x/SIZE_OF_GRIDS),int(32-y/SIZE_OF_GRIDS)});
            assert(g!=grids.end());
            float terrain=g->second->Height(x,y),water=g->second->getLiquidLevel(x,y);
            // This is a terrain intersection, not proof of an invalid position:
            // caves/bridges/dynamic geometry still need separate interpretation.
            if(terrain>INVALID_HEIGHT && water<terrain && terrain-z>1.f) {
                ++dryBelow;
                if(terrain-z>maxDepth) { maxDepth=terrain-z; worst[0]=x;worst[1]=y;worst[2]=z; }
            }
        }
        printf("hypothetical_direct_line=%zu samples=%d dry_terrain_below_samples=%d max_depth=%.5f worst=(%.5f,%.5f,%.5f)\n",
            i,steps+1,dryBelow,maxDepth,worst[0],worst[1],worst[2]);
        if(dryBelow) sample(1000+int(i),worst[0],worst[1],worst[2]);
        for(int capacity:{1024,4096}) {
            resetQuery(capacity);
            float a[3]={p[1],p[2],p[0]},b[3]={p[4],p[5],p[3]},tmp[3];
            dtPolyRef ar=nearest(p[0],p[1],p[2],tmp),br=nearest(p[3],p[4],p[5],tmp);
            dtPolyRef corridor[200]; int count=0;
            dtStatus status=query->findPath(ar,br,a,b,&filter,corridor,&count,200);
            if(dtStatusFailed(status) || !count) continue;
            if(corridor[count-1]!=br)
                assert(dtStatusSucceed(query->closestPointOnPoly(corridor[count-1],b,b,nullptr)));
            SmoothProbe probe{mesh,query,filter}; float smooth[600]; int length=0;
            dtStatus smoothStatus=probe.FindSmoothPath(a,b,corridor,count,smooth,&length,200);
            float worstDepth=0; int dry=0;
            // Check intermediate linear spline positions, not just vertices.
            for(int k=1;k<length;++k) {
                float const* a=smooth+3*(k-1); float const* b=smooth+3*k;
                int steps=std::max(1,int(std::ceil(std::hypot(b[0]-a[0],b[2]-a[2]))));
                for(int step=0;step<=steps;++step) {
                    float t=float(step)/steps,x=a[2]+t*(b[2]-a[2]),y=a[0]+t*(b[0]-a[0]),z=a[1]+t*(b[1]-a[1]);
                    auto g=grids.find({int(32-x/SIZE_OF_GRIDS),int(32-y/SIZE_OF_GRIDS)});
                    assert(g!=grids.end());
                    float terrain=g->second->Height(x,y),water=g->second->getLiquidLevel(x,y);
                    if(terrain>INVALID_HEIGHT && water<terrain && terrain-z>1.f) {++dry;worstDepth=std::max(worstDepth,terrain-z);}
                }
            }
            printf("raw_smooth_probe=%zu capacity=%d query_status=%x complete_corridor=%d polygons=%d smooth_status=%x points=%d dry_terrain_below_samples=%d max_depth=%.5f\n",
                i,capacity,status,corridor[count-1]==br,count,smoothStatus,length,dry,worstDepth);
        }
    }
    for(int capacity:{1024,2048,4096,8192}) {
        resetQuery(capacity); int full=0;
        for(int i=0;i<5;++i) for(int j=0;j<5;++j) if(i!=j) {
            float a[3]={nodes[i][1],nodes[i][2],nodes[i][0]},b[3]={nodes[j][1],nodes[j][2],nodes[j][0]},tmp[3];
            dtPolyRef ar=nearest(nodes[i][0],nodes[i][1],nodes[i][2],tmp),br=nearest(nodes[j][0],nodes[j][1],nodes[j][2],tmp);
            dtPolyRef path[200]; int count=0;
            auto begin=std::chrono::steady_clock::now();
            dtStatus status=query->findPath(ar,br,a,b,&filter,path,&count,200);
            double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
            bool complete=dtStatusSucceed(status) && count && path[count-1]==br && !(status&(DT_OUT_OF_NODES|DT_PARTIAL_RESULT|DT_BUFFER_TOO_SMALL));
            full+=complete;
            printf("capacity=%d route=%d->%d status=%x polygons=%d complete=%d query_ms=%.3f\n",capacity,i,j,status,count,complete,ms);
        }
        printf("capacity=%d full_directed_node_pairs=%d/20\n",capacity,full);
    }
    dtFreeNavMeshQuery(query); dtFreeNavMesh(mesh);
}
'''
    flags = (args.build / "src/common/CMakeFiles/common.dir/flags.make").read_text()
    includes = shlex.split(re.search(r"^CXX_INCLUDES = (.*)$", flags, re.M).group(1))
    defines = shlex.split(re.search(r"^CXX_DEFINES = (.*)$", flags, re.M).group(1))
    libraries = [args.build / p for p in ("src/common/libcommon.a", "dep/recastnavigation/Detour/libDetour.a",
                 "dep/fmt/libfmt.a", "dep/g3dlite/libg3dlib.a")]
    with tempfile.TemporaryDirectory(prefix="loa-bg-nav-audit-") as tmp:
        cpp, exe = Path(tmp) / "audit.cpp", Path(tmp) / "audit"
        cpp.write_text(source)
        subprocess.run([args.compiler, "-std=c++20", "-g", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", *includes, *defines,
                        str(cpp), *map(str, libraries), "-lboost_filesystem", "-lboost_program_options",
                        "-lboost_iostreams", "-lboost_regex", "-lboost_locale", "-lboost_chrono",
                        "-lboost_thread", "-lboost_atomic", "-lssl", "-lcrypto", "-lz", "-pthread",
                        "-o", str(exe)], check=True)
        for i, xyz in enumerate(points, 5):
            print(f"logged_sample={i} xyz={xyz}", flush=True)
        env = dict(os.environ)
        env["UBSAN_OPTIONS"] = env.get("UBSAN_OPTIONS", "") + ":halt_on_error=1:print_stacktrace=1"
        env["ASAN_OPTIONS"] = env.get("ASAN_OPTIONS", "") + ":halt_on_error=1:detect_leaks=1"
        subprocess.run([str(exe), str(args.data)], input="".join(" ".join(map(str, p)) + "\n" for p in points),
                       text=True, check=True, env=env)


if __name__ == "__main__":
    main()
