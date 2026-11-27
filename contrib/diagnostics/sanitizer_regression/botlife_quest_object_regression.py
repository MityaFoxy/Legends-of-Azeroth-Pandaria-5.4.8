#!/usr/bin/env python3
"""Exercise live-object checks and native credit observation using controlled APIs."""
from pathlib import Path
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
module = root / 'modules/mod_botlife/src'
source = (module / 'BotLifeQuestObject.cpp').read_text().split('namespace BotLife', 1)[1]
assert all(token not in source for token in ('KillCreditGO(', 'SetQuestStatus(', 'CompleteQuest('))

mocks = r'''
#include "BotLifeQuestObject.h"
#include <cassert>
#include <cmath>
#include <string_view>
using uint32 = uint32_t;
enum { GAMEOBJECT_TYPE_GOOBER=10, GO_READY=1, GO_STATE_READY=1, GAMEOBJECT_FIELD_FLAGS=1,
       GO_FLAG_IN_USE=1, GO_FLAG_LOCKED=2, GO_FLAG_INTERACT_COND=4, GO_FLAG_NOT_SELECTABLE=16,
       QUEST_STATUS_INCOMPLETE=3, UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2,
       UNIT_STATE_LOST_CONTROL=4, CMSG_GAMEOBJ_USE=1 };
struct GameObjectTemplate {
    uint32 type=GAMEOBJECT_TYPE_GOOBER, ScriptId=0;
    uint32 displayId=20;
    std::string AIName;
    struct { int questId=0; uint32 lockId=0,eventId=0,pageId=0,spellId=0,linkedTrapId=0,
        gossipID=0,WorldStateSetsState=0,conditionID1=0; } goober;
};
struct WorldPacket { WorldPacket(int,int) {} };
namespace G3D {
struct Vector3 { float x,y,z; };
struct Quat {
    Quat toRotationMatrix() const { return {}; }
    Vector3 operator*(Vector3 v) const { return v; }
};
}
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
struct DisplayBounds { float minX=-1,minY=-1,minZ=0,maxX=1,maxY=1,maxZ=0.6f; };
struct DisplayStore {
    DisplayBounds bounds;
    DisplayBounds const* LookupEntry(uint32 id) const { return id==20 ? &bounds : nullptr; }
} sGameObjectDisplayInfoStore;
namespace WorldPackets::GameObject {
struct GameObjUse { explicit GameObjUse(WorldPacket) {} uint32 Guid=0; };
}
struct Player;
struct Map;
struct GameObject {
    Map* map=nullptr;
    GameObjectTemplate info;
    bool world=true, spawned=true, near=true;
    uint32 phase=1, flags=0, lootState=GO_READY, goState=GO_STATE_READY;
    bool IsInWorld() const { return world; }
    bool isSpawned() const { return spawned; }
    Map* GetMap() const { return map; }
    uint32 GetEntry() const { return 204777; }
    uint32 GetPhaseMask() const { return phase; }
    uint32 GetOwnerGUID() const { return 0; }
    uint32 GetScriptId() const { return 0; }
    bool AI() const { return true; }
    GameObjectTemplate const* GetGOInfo() const { return &info; }
    uint32 getLootState() const { return lootState; }
    uint32 GetGoState() const { return goState; }
    bool HasFlag(int, uint32 mask) const { return flags & mask; }
    bool IsAtInteractDistance(Player const*) const { return near; }
    float GetObjectScale() const { return 1; }
    float GetPositionX() const { return 0; }
    float GetPositionY() const { return 0; }
    float GetPositionZ() const { return 0; }
    G3D::Quat GetWorldRotation() const { return {}; }
    uint32 GetGUID() const { return 71; }
};
struct Map {
    GameObject* object=nullptr;
    bool surfaceVisible=false;
    GameObject* GetGameObjectBySpawnId(uint32 guid) { return guid==157304 ? object : nullptr; }
    bool isInLineOfSight(float, float, float eyes, float x, float y, float z, uint32 phase, VMAP::ModelIgnoreFlags) const {
        assert(eyes==1.5f && x==0 && y==0 && std::abs(z-0.65f)<0.0001f && phase==1);
        return surfaceVisible;
    }
};
struct Player {
    Map map;
    uint32 status=QUEST_STATUS_INCOMPLETE, counter=0, calls=0;
    bool combat=false, los=true, grant=true, visible=true;
    bool IsInWorld() const { return true; }
    bool IsDuringRemoveFromWorld() const { return false; }
    uint32 GetMapId() const { return 0; }
    uint32 GetPhaseMask() const { return 1; }
    Map* GetMap() { return &map; }
    Player* GetSession() { return this; }
    uint32 GetQuestObjectiveCounter(uint32) const { return counter; }
    uint32 GetQuestStatus(uint32) const { return status; }
    bool IsAlive() const { return true; }
    bool GetGroup() const { return false; }
    bool IsInCombat() const { return combat; }
    bool IsMounted() const { return false; }
    bool HasUnitState(uint32) const { return false; }
    bool IsNonMeleeSpellCasted(bool) const { return false; }
    bool IsInMap(GameObject const* object) const { return object->map==&map && object->world; }
    bool CanSeeOrDetect(GameObject const*, bool implicit, bool distance) const { assert(!implicit && distance); return visible; }
    bool IsWithinLOSInMap(GameObject const*) const { return los; }
    float GetPositionX() const { return 0; }
    float GetPositionY() const { return 0; }
    float GetPositionZ() const { return 0; }
    float GetCollisionHeight() const { return 1.5f; }
    void HandleGameObjectUseOpcode(WorldPackets::GameObject::GameObjUse& packet) {
        assert(packet.Guid==71); ++calls; if (grant) ++counter;
    }
};
'''
tests = r'''
int main() {
    using namespace BotLife;
    QuestPlanData data{26717,"The Yorgen Worgen",QuestPlanReason::None,{}, {},
        {{266720,204777,1,{},QuestObjectiveKind::GameObject}}};
    QuestSpawn target{157304,204777,0,1,0,0,0};
    for (int scenario=0;scenario<13;++scenario) {
        Player player;
        GameObject object;
        player.map.object=&object;
        object.map=&player.map;
        assert(FindQuestObject(player,target)==&object);
        object.phase=2;
        assert(!FindQuestObject(player,target));
        object.phase=1;
        object.spawned=false;
        assert(!FindQuestObject(player,target));
        object.spawned=true;
        if (scenario==1) object.flags=GO_FLAG_LOCKED;
        if (scenario==2) object.lootState=0;
        if (scenario==3) object.near=false;
        if (scenario==4) player.los=false;
        if (scenario==5) object.info.goober.spellId=5;
        if (scenario==6) object.info.goober.questId=12;
        if (scenario==7) player.combat=true;
        if (scenario==8) player.grant=false;
        if (scenario==9) player.status=0;
        if (scenario==10) object.flags=GO_FLAG_IN_USE;
        if (scenario==11) player.visible=false;
        if (scenario==12) { player.los=false; player.map.surfaceVisible=true; }
        char const* expected[]={"used","object-not-ready","object-not-ready","object-out-of-range",
            "object-line-of-sight-blocked","object-unsupported","object-unsupported","object-interaction-blocked",
            "object-no-quest-progress","object-objective-inactive","object-not-ready","object-not-visible","used"};
        QuestObjectUseResult const result=TryUseQuestObject(player,object,data);
        assert(result.reason==std::string_view(expected[scenario]));
        assert(result.retryable==(scenario==2 || scenario==7 || scenario==10));
        assert(player.counter==(scenario==0 || scenario==12));
        assert(player.calls==(scenario==0 || scenario==8 || scenario==12));
    }
}
'''
with tempfile.TemporaryDirectory(prefix='botlife-object-') as directory:
    cpp = Path(directory) / 'object.cpp'
    binary = Path(directory) / 'object'
    cpp.write_text(mocks + '\nnamespace BotLife' + source + tests)
    subprocess.run([compiler, '-std=c++20', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-UNDEBUG', '-I', str(module), str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
