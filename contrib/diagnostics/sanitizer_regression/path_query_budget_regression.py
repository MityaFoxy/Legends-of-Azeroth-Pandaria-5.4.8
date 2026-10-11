#!/usr/bin/env python3
"""Actual PathGenerator query ownership with real Detour and small world doubles."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
text = (root / "src/server/game/Movement/PathGenerator.cpp").read_text()


def method(signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


source = r'''
#include "DetourNavMesh.h"
#include "DetourNavMeshQuery.h"
#include "DetourNode.h"
#include "DetourAlloc.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
using uint32 = std::uint32_t;
constexpr int PATHFIND_BLANK=0, MAX_POINT_PATH_LENGTH=200;
namespace G3D { struct Vector3 { static Vector3 zero() { return {}; } }; }
struct Guid { unsigned GetCounter() const { return 1; } };
struct WorldObject {
    Guid GetGUID() const { return {}; }
    unsigned GetMapId() const { return 529; }
    unsigned GetInstanceId() const { return 1; }
};
namespace DisableMgr {
bool enabled=true;
bool IsPathfindingEnabled(unsigned) { return enabled; }
}
namespace MMAP {
struct MMapManager {
    dtNavMesh* mesh=nullptr;
    dtNavMeshQuery* shared=nullptr;
    dtNavMesh* GetNavMesh(unsigned) { return mesh; }
    dtNavMeshQuery* GetNavMeshQuery(unsigned,unsigned) { return shared; }
} manager;
struct MMapFactory { static MMapManager* createOrGetMMapManager() { return &manager; } };
}
unsigned warnings=0;
#define TC_LOG_DEBUG(...) ((void)0)
#define TC_LOG_WARN(...) (++warnings)
struct PathGenerator {
    dtPolyRef _pathPolyRefs[200];
    uint32 _polyLength;
    int _type;
    bool _useStraightPath, _forceDestination;
    uint32 _pointPathLimit;
    G3D::Vector3 _endPosition;
    WorldObject const* _source;
    dtNavMesh const* _navMesh;
    dtNavMeshQuery const* _navMeshQuery;
    struct QueryDeleter {
        void operator()(dtNavMeshQuery* query) const { dtFreeNavMeshQuery(query); }
    };
    std::unique_ptr<dtNavMeshQuery,QueryDeleter> _privateQuery;
    uint32 _queryNodeLimit=0;
    bool _useRaycast;
    int* visualizePathWaypointGUIDs=nullptr;
    int* visualizeNavmeshWaypointGUIDs=nullptr;
    void CreateFilter() {}
    explicit PathGenerator(WorldObject const*,uint32=0);
    ~PathGenerator();
};
''' + method("PathGenerator::PathGenerator(") + "\n" + method("PathGenerator::~PathGenerator()") + r'''
std::size_t live=0;
bool failNext=false;
void* allocate(std::size_t bytes,dtAllocHint) {
    if(failNext) { failNext=false; return nullptr; }
    void* p=std::malloc(bytes);
    if(p) ++live;
    return p;
}
void release(void* p) { if(p) { assert(live); --live; std::free(p); } }
int main() {
    dtAllocSetCustom(allocate,release);
    auto& m=MMAP::manager;
    m.mesh=dtAllocNavMesh(); assert(m.mesh);
    dtNavMeshParams params{};
    params.tileWidth=533.3333f; params.tileHeight=533.3333f;
    params.maxTiles=16; params.maxPolys=256;
    assert(dtStatusSucceed(m.mesh->init(&params)));
    m.shared=dtAllocNavMeshQuery(); assert(m.shared);
    assert(dtStatusSucceed(m.shared->init(m.mesh,1024)));
    auto baseline=live;
    WorldObject owner;
    {
        PathGenerator normal(&owner);
        assert(normal._navMeshQuery==m.shared && normal._queryNodeLimit==1024);
        assert(live==baseline && !normal._privateQuery);
    }
    {
        PathGenerator bot(&owner,4096), other(&owner,8192);
        assert(bot._navMeshQuery!=m.shared && other._navMeshQuery!=bot._navMeshQuery);
        assert(bot._queryNodeLimit==4096 && other._queryNodeLimit==4096);
        assert(bot._navMeshQuery->getNodePool()->getMaxNodes()==4096);
        assert(other._navMeshQuery->getNodePool()->getMaxNodes()==4096);
        assert(m.shared->getNodePool()->getMaxNodes()==1024);
    }
    assert(live==baseline); // every private query and all its pools were freed
    {
        PathGenerator tiny(&owner,1);
        assert(tiny._privateQuery && tiny._queryNodeLimit==1024);
        assert(tiny._navMeshQuery->getNodePool()->getMaxNodes()==1024);
    }
    assert(live==baseline);
    {
        failNext=true; PathGenerator bot(&owner,4096);
        assert(warnings==1 && bot._navMeshQuery==m.shared);
        assert(bot._queryNodeLimit==1024 && !bot._privateQuery && live==baseline);
    }
    {
        DisableMgr::enabled=false;
        PathGenerator disabled(&owner,4096);
        assert(!disabled._navMeshQuery && !disabled._privateQuery && !disabled._queryNodeLimit);
        assert(live==baseline); DisableMgr::enabled=true;
    }
    auto* mesh=m.mesh; auto* shared=m.shared;
    m.mesh=nullptr; m.shared=nullptr;
    {
        PathGenerator missing(&owner,4096);
        assert(!missing._navMeshQuery && !missing._privateQuery && !missing._queryNodeLimit);
        assert(live==baseline);
    }
    m.mesh=mesh;
    {
        // A loaded mesh can be queried even if there is no cached instance query.
        PathGenerator uncached(&owner,4096);
        assert(uncached._privateQuery && uncached._queryNodeLimit==4096);
    }
    assert(live==baseline);
    dtFreeNavMeshQuery(shared); dtFreeNavMesh(mesh); assert(live==0);
    dtAllocSetCustom(nullptr,nullptr);
}
'''
detour = root / "dep/recastnavigation/Detour"
with tempfile.TemporaryDirectory(prefix="loa-path-query-budget-") as tmp:
    binary = pathlib.Path(tmp) / "regression"
    subprocess.run([sys.argv[2], "-x", "c++", "-std=c++20", "-O1", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                    "-I", str(detour / "Include"), "-", *map(str, sorted((detour / "Source").glob("*.cpp"))),
                    "-o", str(binary)], input=source, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("Private 4096-node bot query, shared 1024-node isolation, cap, allocation fallback and ownership passed")
