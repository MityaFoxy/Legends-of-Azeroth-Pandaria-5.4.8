#!/usr/bin/env python3
"""Run the actual opt-in BG controller with session/AI doubles under ASan/UBSan.

Packet round trips use the real core handlers' parsing prefixes. Not a substitute
for live BG geometry, spell data, queue matching or full-cycle soak gates.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
path = root / "modules/mod_playerbots/src/Manager/BattlegroundTestController.cpp"
controller = "\n".join(line for line in path.read_text().splitlines() if not line.startswith("#include"))
handlers = (root / "src/server/game/Handlers/BattleGroundHandler.cpp").read_text()
join = handlers[handlers.index("    for (int i = 0; i < 2; i++) // blacklistedMapIds") : handlers.index("    if (hasRoleMask)")]
port = handlers[handlers.index("    recvData >> action >> queueSlot >> id >> time;") : handlers.index("    if (!_player->InBattlegroundQueue())", handlers.index("void WorldSession::HandleBattleFieldPortOpcode"))]
misc = (root / "src/server/game/Handlers/MiscHandler.cpp").read_text()
start = misc.index("void WorldSession::HandleAreaSpiritHealerQueueOpcode")
spirit = misc[misc.index("    guid[5] = recvData.ReadBit();", start) : misc.index("    Creature* unit =", start)]
assert 'GetBoolDefault("AiPlayerbot.BattlegroundTest", false)' in (root / "modules/mod_playerbots/src/Utils/PlayerbotAIConfig.cpp").read_text()
assert "BattlegroundTest::Update(diff)" in (root / "modules/mod_playerbots/src/mod_playerbots.cpp").read_text()
playerbot_ai_source = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.cpp").read_text()
assert "BattlegroundTest::DoNextAction(this)" in playerbot_ai_source
master_guard_start = playerbot_ai_source.index("// Battleground raids are temporary matchmaker groups.")
master_guard_end = playerbot_ai_source.index("if (master && master->IsInWorld())", master_guard_start)
master_guard = playerbot_ai_source[master_guard_start:master_guard_end]
assert "&& group && !bot->InBattleground())" in master_guard
assert master_guard.index("!bot->InBattleground()") < master_guard.index("botAI->SetMaster(newMaster)")
bracket_source = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotBracketMgr.cpp").read_text()
assert "!CanPlayerLeaveStartingArea(player)" in bracket_source
assert "!player->InBattleground()" in bracket_source
assert "!player->InBattlegroundQueue()" in bracket_source
world_config = (root / "src/server/worldserver/worldserver.conf.dist").read_text()
assert "Battleground.IgnoreFaction = 0" in world_config
battleground_source = (root / "src/server/game/Battlegrounds/Battleground.cpp").read_text()
add_player = battleground_source[battleground_source.index("void Battleground::AddPlayer(Player* player)"):
    battleground_source.index("void Battleground::AddPlayer(Player* player)") + 9000]
for flight_cleanup in ("SPELL_AURA_FLY", "SPELL_AURA_MOD_INCREASE_MOUNTED_FLIGHT_SPEED",
                       "SetCanFly(false)", "SetDisableGravity(false)"):
    assert flight_cleanup in add_player
battleground_mgr_source = (root / "src/server/game/Battlegrounds/BattlegroundMgr.cpp").read_text()
apply_deserter = battleground_mgr_source[battleground_mgr_source.index("void BattlegroundMgr::ApplyDeserter"):
    battleground_mgr_source.index("void BattlegroundMgr::EnqueueNewGameStat")]
assert "guid.GetRawValue()" in apply_deserter
assert "guidLow, guid, SPELL_DESERTER" not in apply_deserter

source = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <vector>
using uint8=std::uint8_t; using uint32=std::uint32_t; using uint64=std::uint64_t;
using int8=std::int8_t; using int32=std::int32_t;
constexpr int BATTLEGROUND_AB=3, STATUS_WAIT_LEAVE=4, STATUS_IN_PROGRESS=3,
    STATUS_WAIT_JOIN=2, TEAM_ALLIANCE=0, TEAM_HORDE=1, ALLIANCE=469, HORDE=67,
    PLAYER_FLAGS_GHOST=1, SPELL_WAITING_FOR_RESURRECT=2, UNIT_STATE_CASTING=4,
    BG_CREATURE_ENTRY_A_SPIRITGUIDE=13116, BG_CREATURE_ENTRY_H_SPIRITGUIDE=13117,
    BG_AB_DYNAMIC_NODES_COUNT=5, BG_AB_OBJECT_BANNER_NEUTRAL=0,
    BG_AB_OBJECT_BANNER_CONT_A=1, BG_AB_OBJECT_BANNER_CONT_H=2,
    BG_AB_OBJECT_BANNER_ALLY=3, BG_AB_OBJECT_BANNER_HORDE=4,
    CMSG_BATTLEMASTER_JOIN=1, CMSG_BATTLEFIELD_PORT=2, CMSG_REPOP_REQUEST=3,
    CMSG_AREA_SPIRIT_HEALER_QUEUE=4, CMSG_BATTLEFIELD_LEAVE=5,
    CMSG_CANCEL_MOUNT_AURA=6, BOT_STATE_COMBAT=0, SPELL_ATTR2_CAN_TARGET_NOT_IN_LOS=4,
    CURRENT_GENERIC_SPELL=0, INVENTORY_SLOT_BAG_0=0, EQUIPMENT_SLOT_START=0,
    EQUIPMENT_SLOT_BODY=3, EQUIPMENT_SLOT_TABARD=18, EQUIPMENT_SLOT_END=19;
constexpr float INTERACTION_DISTANCE=5;
constexpr float INVALID_HEIGHT=-100000;
const float BG_AB_NodePositions[5][4] = {};
const float BG_AB_DoorPositions[2][8] = {
    {1284.597f,1281.167f,0,0,0,0,0,0},
    {708.0903f,708.4479f,0,0,0,0,0,0}
};
using BattlegroundQueueTypeId=int;
uint32 tick=10000;
uint32 getMSTime() {return tick;}
uint32 getMSTimeDiff(uint32 a,uint32 b) {return b-a;}
namespace GameTime { uint64 GetGameTime() {return 100;} }
namespace VMAP { enum class ModelIgnoreFlags { Nothing }; }
namespace Trinity { bool IsValidMapCoord(float x,float y,float z) {return std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z);} }
struct Position {float x,y,z;};
struct ObjectGuid {
    uint64 value=0;
    ObjectGuid()=default; explicit ObjectGuid(uint64 v):value(v){}
    uint8& operator[](int i) {return reinterpret_cast<uint8*>(&value)[i];}
    uint8 operator[](int i) const {return reinterpret_cast<uint8 const*>(&value)[i];}
    uint32 GetCounter() const {return value & 0xffffffff;}
    bool operator<(ObjectGuid const& b) const {return value<b.value;}
    bool operator==(ObjectGuid const& b) const {return value==b.value;}
};
struct WorldPacket {
    std::vector<uint8> data; size_t bitWrite=0, bitRead=0;
    explicit WorldPacket(int) {}
    void WriteBit(bool v) {
        if (bitWrite%8==0) data.push_back(0);
        if(v) data.back() |= uint8(1u<<(7-bitWrite%8));
        ++bitWrite;
    }
    void FlushBits() {bitWrite=(bitWrite+7)/8*8;}
    bool ReadBit() {
        assert(bitRead/8 < data.size());
        bool v=data[bitRead/8] & (1u<<(7-bitRead%8)); ++bitRead; return v;
    }
    template<class T> WorldPacket& operator<<(T v) {
        FlushBits(); auto p=reinterpret_cast<uint8*>(&v); data.insert(data.end(),p,p+sizeof v);
        bitWrite=data.size()*8; return *this;
    }
    template<class T> WorldPacket& operator>>(T& v) {
        bitRead=(bitRead+7)/8*8; assert(bitRead/8+sizeof v<=data.size());
        std::memcpy(&v,data.data()+bitRead/8,sizeof v); bitRead+=sizeof v*8; return *this;
    }
    template<class T> void read_skip() {T v; *this>>v;}
    void WriteByteSeq(uint8 b) {if(b) *this<<uint8(b^1);}
    void ReadByteSeq(uint8& b) {if(b) {uint8 v; *this>>v; b^=v;}}
};
struct Player; struct PlayerbotAI; struct Item {};
struct SpellInfo {
    uint32 Id=21651; bool ignoreLos=false;
    bool HasAttribute(int) const {return ignoreLos;}
};
struct Spell {SpellInfo info; SpellInfo* GetSpellInfo(){return &info;}};
struct SpellMgr {
    SpellInfo opening; bool available=true;
    SpellInfo* GetSpellInfo(int id){assert(id==21651);return available?&opening:nullptr;}
} spellMgr;
auto sSpellMgr=&spellMgr;
struct Creature {ObjectGuid guid{0x123456789aULL}; bool alive=false,service=true; bool IsSpiritService(){return service;} ObjectGuid GetGUID(){return guid;}};
struct GameObject {
    bool spawned=false, nearby=true, los=true; float x=0,y=0,z=0; ObjectGuid guid{1};
    bool isSpawned(){return spawned;} bool IsAtInteractDistance(Player*,SpellInfo const*){return nearby;}
    ObjectGuid GetGUID(){return guid;} float GetPositionX(){return x;} float GetPositionY(){return y;} float GetPositionZ(){return z;}
    void GetHitSpherePointFor(Position const& p,float& ox,float& oy,float& oz){ox=p.x;oy=p.y;oz=p.z;}
};
struct Map {bool los=true; bool isInLineOfSight(float,float,float,float,float,float,uint32,VMAP::ModelIgnoreFlags){return los;}};
struct BattlegroundScore {};
struct Battleground {
    int type=BATTLEGROUND_AB,status=STATUS_WAIT_JOIN; bool rated=false; uint32 id=1;
    Map* activeMap=nullptr; uint32 objectLookups=0;
    GameObject objects[40];
    std::map<ObjectGuid,BattlegroundScore*> scores;
    auto GetPlayerScoresBegin(){return scores.begin();} auto GetPlayerScoresEnd(){return scores.end();}
    int GetTypeID(){return type;} bool IsRated(){return rated;}
    uint32 GetInstanceID(){return id;} int GetStatus(){return status;}
    uint32 GetTeamScore(int){return 0;}
    void GetTeamStartLoc(uint32 team,float& x,float& y,float& z,float& o){
        if(team==ALLIANCE){x=1313.9f;y=1310.74f;z=-9.01043f;}
        else{x=684.014f;y=681.22f;z=-12.9159f;}
        o=0;
    }
    Map* FindBgMap(){return activeMap;}
    GameObject* GetBGObject(uint32 i){assert(activeMap && i<40);++objectLookups;return &objects[i];}
};
struct WorldSession {
    Player* bot=nullptr; int joins=0,accepts=0,leaves=0,releases=0,revives=0;
    uint32 GetAccountId(){return 123;}
    void HandleBattlemasterJoinOpcode(WorldPacket&);
    void HandleBattleFieldPortOpcode(WorldPacket&);
    void HandleRepopRequestOpcode(WorldPacket&);
    void HandleAreaSpiritHealerQueueOpcode(WorldPacket&);
    void HandleBattlefieldLeaveOpcode(WorldPacket&);
    void HandleCancelMountAuraOpcode(WorldPacket&);
};
struct Player {
    ObjectGuid guid{1}; WorldSession session; Battleground* bg=nullptr; PlayerbotAI* ai=nullptr;
    bool world=true,teleport=false,alive=true,combat=false,queue=false,invited=false,
        group=false,ghost=false,waiting=false,casting=false,mounted=false,access=true,
        afk=false,nearGuide=true,hasGuide=true,los=true,canLeaveStartingArea=true;
    int moves=0,casts=0,stops=0,team=ALLIANCE;
    bool moving=false,castAccepted=true; float x=0,y=0,z=0; Map map;
    Creature guide; Item item; uint32 level=20,equippedItems=1,saves=0;
    Spell current;
    Player(){session.bot=this;}
    ObjectGuid GetGUID(){return guid;} WorldSession* GetSession(){return &session;}
    bool IsInWorld(){return world;} bool IsBeingTeleported(){return teleport;} uint32 GetInstanceId(){return bg?bg->id:0;}
    bool IsInFlight(){return false;} uint32 GetLevel(){return level;}
    Item* GetItemByPos(uint8 bag,uint8 slot){assert(bag==INVENTORY_SLOT_BAG_0);return slot<equippedItems?&item:nullptr;}
    void SaveToDB(bool){++saves;}
    Battleground* GetBattleground(){return bg;} bool IsAlive(){return alive;}
    bool IsInCombat(){return combat;} bool GetGroup(){return group;}
    bool GetBGAccessByLevel(int){return access;} bool InBattlegroundQueue(){return queue;}
    bool IsInvitedForBattlegroundQueueType(int){return invited;}
    uint32 GetBattlegroundQueueIndex(int){return 2;}
    bool HasPlayerFlag(int){return ghost;} bool HasAura(int){return waiting;}
    bool HasUnitState(int){return casting;} bool IsMounted(){return mounted;}
    Spell* GetCurrentSpell(int){return casts && castAccepted ? &current : nullptr;}
    int GetBGTeam(){return team;} bool IsWithinDistInMap(Creature*,float){return nearGuide;}
    Creature* FindNearestCreature(uint32,float,bool alive){return hasGuide && guide.alive==alive ? &guide : nullptr;}
    bool IsWithinLOSInMap(GameObject* o){return los && o->los;}
    float GetDistance2d(float ox,float oy){return std::hypot(x-ox,y-oy);}
    float GetDistance2d(GameObject* o){return GetDistance2d(o->x,o->y);}
    float GetPositionX(){return x;} float GetPositionY(){return y;} float GetPositionZ(){return z;}
    float GetMapHeight(float,float,float,bool=true,float=50){return 0;} float GetCollisionHeight(){return 2;}
    Map* GetMap(){return &map;} uint32 GetPhaseMask(){return 1;}
    bool isMoving(){return moving;}
    void StopMoving(){moving=false;++stops;} void CastSpell(GameObject*,int id,bool triggered){assert(id==21651&&!triggered);++casts;}
    bool isAFK(){return afk;} void ToggleAFK(){afk=!afk;}
};
bool CanPlayerLeaveStartingArea(Player const* player){return player->canLeaveStartingArea;}
struct PlayerbotAI {
    Player* bot; bool real=false,master=false; int state=1; uint32 delay=0;
    PlayerbotAI(Player* b):bot(b){bot->ai=this;}
    Player* GetBot(){return bot;} bool IsRealPlayer(){return real;}
    bool HasRealPlayerMaster(){return master;} int GetState(){return state;}
    void SetNextCheckDelay(uint32 v){delay=v;}
};
struct Config {bool battlegroundTest=false,account=true;float sightDistance=60;bool IsInRandomAccountList(uint32){return account;}} config;
Config* sPlayerbotAIConfig=&config;
struct Manager {
    std::map<uint64,Player*> bots;
    std::map<uint64,uint32> targets;
    std::set<uint64> pending;
    uint32 randomizes=0;
    auto GetPlayerBotsBegin(){return bots.begin();} auto GetPlayerBotsEnd(){return bots.end();}
    uint32 GetValue(Player* bot,std::string const&){auto i=targets.find(bot->guid.value);return i==targets.end()?bot->level:i->second;}
    bool HasPendingRandomization(Player* bot){return pending.contains(bot->guid.value);}
    void Randomize(Player* bot){++randomizes;bot->level=GetValue(bot,"level");bot->equippedItems=1;bot->teleport=true;pending.erase(bot->guid.value);}
} manager;
Manager* sRandomPlayerbotMgr=&manager;
uint32 equipmentRepairs=0;
struct BotFactory {
    Player* bot;
    BotFactory(Player* player,uint32):bot(player){}
    void InitEquipment(bool){++equipmentRepairs;bot->equippedItems=1;}
};
struct BattlegroundMgr {static int BGQueueTypeId(int,int){return 1;}};
#define GET_PLAYERBOT_AI(bot) ((bot)->ai)
std::vector<std::string> phases;
template<class... T> void recordLog(char const*,char const*,T&&...){ }
#define TC_LOG_INFO(...) do { phases.emplace_back(phase); } while(false)
struct Event {};
struct MovementAction {
    Player* bot;
    MovementAction(PlayerbotAI* ai,char const*):bot(ai->GetBot()){}
    virtual bool Execute(Event){return false;}
    bool MoveTo(uint32,float,float,float,bool=false,bool=false,bool=false){++bot->moves;bot->moving=true;return true;}
    bool MoveNear(Creature*,float){++bot->moves;return true;}
};
struct AttackEnemyPlayerAction {
    PlayerbotAI* ai; static bool enemy;
    explicit AttackEnemyPlayerAction(PlayerbotAI* a):ai(a){}
    bool isUseful(){return true;}
    bool Execute(Event){if(enemy){ai->state=0;return true;}return false;}
};
bool AttackEnemyPlayerAction::enemy=false;
namespace BattlegroundTest {void Update(uint32);bool DoNextAction(PlayerbotAI*);}
'''
# Protocol-prefix checks exercise the controller writers against current handler readers.
source += '''
void WorldSession::HandleBattlemasterJoinOpcode(WorldPacket& recvData) {
    ObjectGuid guid; uint8 asGroup; bool hasRoleMask;
''' + join + r'''
    assert(!asGroup && !hasRoleMask && guid.GetCounter()==BATTLEGROUND_AB);
    ++joins;bot->queue=true;
}
void WorldSession::HandleBattleFieldPortOpcode(WorldPacket& recvData) {
    ObjectGuid guid; uint8 action; uint32 queueSlot,id,time;
''' + port + r'''
    assert(action==1 && queueSlot==2 && guid.value==0);
    ++accepts;bot->queue=false;bot->invited=false;
}
void WorldSession::HandleRepopRequestOpcode(WorldPacket&) {++releases;bot->ghost=true;}
void WorldSession::HandleCancelMountAuraOpcode(WorldPacket&) {bot->mounted=false;}
void WorldSession::HandleAreaSpiritHealerQueueOpcode(WorldPacket& recvData) {
    ObjectGuid guid;
''' + spirit + r'''
    assert(guid.value==bot->guide.guid.value);++revives;bot->waiting=true;
}
void WorldSession::HandleBattlefieldLeaveOpcode(WorldPacket&) {
    assert(bot->bg && bot->bg->status==STATUS_WAIT_LEAVE);
    ++leaves;bot->bg=nullptr;bot->group=false;
}
'''
# Logging arguments are intentionally unevaluated by the double; real TU compile
# validates the format/Player API. Geometry remains the native movement contract.
source = source.replace('bool IsInWorld(){return world;}', 'uint32 GetMapId(){return 529;} bool IsInWorld(){return world;}')
source += controller
source += r'''
int main() {
    Player bot; PlayerbotAI ai(&bot); manager.bots[1]=&bot;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    config.battlegroundTest=true; ai.real=true;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    ai.real=false;ai.master=true;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    ai.master=false;bot.group=true;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    bot.group=false;bot.access=false;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    bot.access=true;bot.canLeaveStartingArea=false;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    bot.canLeaveStartingArea=true;bot.teleport=true;
    BattlegroundTest::Update(1000); assert(bot.session.joins==0);
    bot.teleport=false;tick+=60000;manager.targets[1]=44;manager.pending.insert(1);
    BattlegroundTest::Update(1000);
    assert(bot.session.joins==0 && manager.randomizes==1 && bot.level==44 && bot.teleport);
    BattlegroundTest::Update(1000);assert(bot.session.joins==0);
    bot.teleport=false;bot.equippedItems=0;
    BattlegroundTest::Update(1000);
    assert(bot.session.joins==0 && equipmentRepairs==1 && bot.saves==1 && bot.equippedItems==1);
    BattlegroundTest::Update(1000);assert(bot.session.joins==1);
    BattlegroundTest::Update(1000);assert(bot.session.joins==1 && !bot.session.accepts);
    bot.invited=true;tick+=5000;BattlegroundTest::Update(1000);assert(bot.session.accepts==1);
    Battleground bg;bot.bg=&bg;bg.activeMap=&bot.map;
    BattlegroundTest::Update(1000);assert(!bot.session.leaves);
    assert(BattlegroundTest::DoNextAction(&ai) && bot.moves==1);
    State& preparation=states.at(bot.guid);
    assert(preparation.preparationSet && preparation.preparationSlot<15);
    assert(std::hypot(preparation.preparationX-1313.9f,preparation.preparationY-1310.74f)>1.0f);
    Player teammate;teammate.guid=ObjectGuid(2);teammate.bg=&bg;teammate.team=ALLIANCE;
    State teammateState;teammateState.instance=bg.id;teammateState.team=ALLIANCE;
    states[teammate.guid]=teammateState;
    assert(SelectPreparationPosition(&teammate,&bg,states.at(teammate.guid)));
    assert(states.at(teammate.guid).preparationSlot!=preparation.preparationSlot);
    assert(preparation.preparationInstance==bg.id
        && states.at(teammate.guid).preparationInstance==bg.id);
    assert(std::hypot(states.at(teammate.guid).preparationX-preparation.preparationX,
        states.at(teammate.guid).preparationY-preparation.preparationY)>=2.9f);
    bot.x=preparation.preparationX;bot.y=preparation.preparationY;bot.z=preparation.preparationZ;
    bot.moving=false;int preparationMoves=bot.moves;
    assert(BattlegroundTest::DoNextAction(&ai) && bot.moves==preparationMoves);
    bg.status=STATUS_IN_PROGRESS;
    assert(BattlegroundTest::DoNextAction(&ai) && bot.moves==preparationMoves+1 && ai.delay==1000);
    int objectiveMoves=bot.moves;
    bot.combat=true;assert(!BattlegroundTest::DoNextAction(&ai));bot.combat=false;
    bot.casting=true;BattlegroundTest::DoNextAction(&ai);assert(bot.moves==objectiveMoves);bot.casting=false;
    AttackEnemyPlayerAction::enemy=true;assert(!BattlegroundTest::DoNextAction(&ai));
    assert(ai.state==BOT_STATE_COMBAT);ai.state=1;AttackEnemyPlayerAction::enemy=false;
    uint32 node=states.at(bot.guid).objective;bg.objects[node*8+BG_AB_OBJECT_BANNER_NEUTRAL].spawned=true;
    bot.x=bot.y=bot.z=0;
    int arrivedMoves=bot.moves;bot.moving=true;int arrivedStops=bot.stops;
    assert(BattlegroundTest::DoNextAction(&ai));
    assert(bot.moves==arrivedMoves && bot.stops==arrivedStops+1 && !bot.moving);
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==arrivedMoves && bot.stops==arrivedStops+1);
    bg.objects[node*8+BG_AB_OBJECT_BANNER_NEUTRAL].nearby=false;
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==++arrivedMoves);
    bg.objects[node*8+BG_AB_OBJECT_BANNER_NEUTRAL].nearby=true;bot.los=false;bot.moving=false;
    // A synthetic WorldObject LOS ray must not override native GameObject spell
    // validation. Once in interaction range no additional movement is issued.
    states.at(bot.guid).approachSet=false;bot.map.los=false;
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==arrivedMoves);
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.casts==1);
    bot.map.los=true;bot.los=true;
    sSpellMgr->available=false;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.casts==1);
    sSpellMgr->available=true;bot.casts=0;
    bg.objects[node*8+BG_AB_OBJECT_BANNER_NEUTRAL].spawned=false;
    bg.objects[node*8+BG_AB_OBJECT_BANNER_ALLY].spawned=true;
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==arrivedMoves); // Friendly node: stay/defend.
    bg.objects[node*8+BG_AB_OBJECT_BANNER_ALLY].spawned=false;
    bg.objects[node*8+BG_AB_OBJECT_BANNER_NEUTRAL].spawned=true;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.casts==1);
    bot.mounted=true;tick+=2000;BattlegroundTest::Update(1000);assert(!bot.mounted&&bot.casts==2);
    bot.casting=true;tick+=2000;BattlegroundTest::Update(1000);assert(bot.casts==2);bot.casting=false;
    bot.castAccepted=false;
    tick+=2000;BattlegroundTest::Update(1000);
    assert(bot.casts==3 && phases.back()=="capture-not-started");
    auto beforeCaptureLogs=std::count(phases.begin(),phases.end(),"capture-not-started");
    tick+=2000;BattlegroundTest::Update(1000);
    assert(std::count(phases.begin(),phases.end(),"capture-not-started")==beforeCaptureLogs);
    tick+=30000;BattlegroundTest::Update(1000);
    assert(std::count(phases.begin(),phases.end(),"capture-not-started")==beforeCaptureLogs+1);
    bot.castAccepted=true;
    bot.alive=false;tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.releases==1);
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==1);
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==1);
    bot.waiting=false;bot.nearGuide=false;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==1);
    int before=bot.moves;BattlegroundTest::DoNextAction(&ai);assert(bot.moves==before+1);
    bot.nearGuide=true;bot.moving=true;before=bot.moves;
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==before && !bot.moving);
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==before);
    // Native Creature::Respawn may switch a guide to ALIVE. Both states work,
    // without changing the interaction range, packet or native wave handling.
    bot.guide.alive=true;bot.waiting=false;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==2);
    bot.waiting=false;bot.nearGuide=false;before=bot.moves;
    BattlegroundTest::DoNextAction(&ai);assert(bot.moves==before+1);
    bot.nearGuide=true;bot.hasGuide=false;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==2);
    bot.hasGuide=true;bot.guide.service=false;
    tick+=2000;BattlegroundTest::Update(1000);assert(bot.session.revives==2);
    bot.guide.service=true;
    bot.alive=true;bot.ghost=false;bot.nearGuide=true;
    tick+=2000;BattlegroundTest::Update(1000);
    assert(std::find(phases.begin(),phases.end(),"resurrected")!=phases.end());
    tick+=5000;bg.status=STATUS_WAIT_LEAVE;BattlegroundTest::Update(1000);assert(bot.session.leaves==1);
    assert(states.at(bot.guid).completed==1);
    tick+=60000;BattlegroundTest::Update(1000);assert(bot.session.joins==2);
    bot.queue=false;bot.bg=&bg;bg.id=2;bg.status=STATUS_WAIT_JOIN;
    // Bot actions can run before the once-per-second lifecycle update after a
    // port. They must not consume the new instance transition or the same-bot
    // re-entry gate will miss the second match.
    assert(BattlegroundTest::DoNextAction(&ai));
    assert(states.at(bot.guid).matches==1);
    BattlegroundTest::Update(1000);assert(states.at(bot.guid).matches==2);
    uint32 objectLookups=bg.objectLookups;int teardownMoves=bot.moves;ai.delay=0;
    bg.activeMap=nullptr;
    assert(!FindBanner(&bg,states.at(bot.guid).objective).object && bg.objectLookups==objectLookups);
    assert(BattlegroundTest::DoNextAction(&ai));
    assert(ai.delay==1000 && bot.moves==teardownMoves && bg.objectLookups==objectLookups);
    tick+=1000;BattlegroundTest::Update(1000);
    assert(bot.moves==teardownMoves && bg.objectLookups==objectLookups);
    bg.activeMap=&bot.map;
    bg.rated=true;assert(!BattlegroundTest::DoNextAction(&ai));
    tick+=10000;BattlegroundTest::Update(1000);assert(bot.session.leaves==1);
    manager.bots.clear();BattlegroundTest::Update(1000);assert(states.empty());
    Player repairA,repairB,repairC;
    repairA.guid=ObjectGuid(11);repairB.guid=ObjectGuid(12);repairC.guid=ObjectGuid(13);
    repairA.equippedItems=repairB.equippedItems=repairC.equippedItems=0;
    State repairStateA,repairStateB,repairStateC;uint32 repairBudget=2;
    uint32 repairsBefore=equipmentRepairs;
    assert(!RepairQueueReadiness(&repairA,repairStateA,tick,repairBudget));
    assert(!RepairQueueReadiness(&repairB,repairStateB,tick,repairBudget));
    assert(!RepairQueueReadiness(&repairC,repairStateC,tick,repairBudget));
    assert(equipmentRepairs==repairsBefore+2 && repairBudget==0);
    assert(repairA.equippedItems==1 && repairB.equippedItems==1 && repairC.equippedItems==0);
    State wrap;wrap.requested=true;wrap.lastRequest=UINT32_MAX-10;
    assert(!RequestReady(wrap,48,60));assert(RequestReady(wrap,49,60));
}
'''
with tempfile.TemporaryDirectory(prefix="loa-bg-test-regression-") as directory:
    cpp = pathlib.Path(directory) / "regression.cpp"
    exe = pathlib.Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
