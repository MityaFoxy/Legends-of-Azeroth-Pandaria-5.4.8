#!/usr/bin/env python3
"""Exercise real party Values, follow and auto-release with bounded world doubles.

Geometry, native spell/repop handlers and the AI engine are doubles: this does
not prove live dungeon traversal, resurrection or healer rotations.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
base = root / "modules/mod_playerbots/src/strategy"


def method(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


values = (base / "value/ValueContext.h").read_text()
triggers = (base / "triggers/TriggerContext.h").read_text()
for key, creator in (("aoe heal", "AoeHealValue"), ("enemy healer target", "EnemyHealerTargetValue")):
    assert f'creators["{key}"]' in values and f"new {creator}(botAI)" in values
for level in ("critical", "low", "medium", "almost full"):
    assert f'creators["{level} aoe heal"]' in triggers
    assert f'new AoeHealTrigger(botAI, "{level} aoe heal", "{level}", 2)' in triggers
for key in ("party member dead", "combat party member dead", "healer should attack"):
    assert f'creators["{key}"]' in triggers
follow = (base / "actions/FollowActions.cpp").read_text()
release = (base / "Dead/ReleaseSpiritAction.cpp").read_text()
methods = "\n".join([
    method((base / "value/AoeHealValue.cpp").read_text(), "uint8 AoeHealValue::Calculate()"),
    method((base / "value/EnemyHealerTargetValue.cpp").read_text(), "Unit* EnemyHealerTargetValue::Calculate()"),
    method((base / "triggers/HealthTriggers.cpp").read_text(), "bool AoeHealTrigger::IsActive()"),
    *(method(follow, signature) for signature in (
        "bool FollowAction::UseGroupFollowFormation()", "bool FollowAction::CanMoveInGroupFormation()",
        "WorldLocation FollowAction::GetGroupFollowLocation()", "bool FollowAction::Execute(",
        "bool FollowAction::isUseful()", "bool FollowAction::CanDeadFollow(")),
    method(release, "bool CanReleaseDungeonSpirit("),
    method(release, "bool AutoReleaseSpiritAction::isUseful()"),
    method(release, "bool AutoReleaseSpiritAction::Execute("),
])

prefix = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <map>
#include <string>
#include <type_traits>
#include <vector>
#include "GroupFollowFormation.h"
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 value = 0;
    bool operator<(ObjectGuid other) const { return value < other.value; }
    bool operator==(ObjectGuid const& other) const = default;
    uint8 operator[](uint8) const { return 0; }
    uint32 GetCounter() const { return value; }
};
using GuidVector = std::vector<ObjectGuid>;
enum CurrentSpellTypes { CURRENT_GENERIC_SPELL, CURRENT_CHANNELED_SPELL };
enum { BOT_STATE_NON_COMBAT, BOT_STATE_COMBAT, UNIT_STATE_IN_FLIGHT,
    PLAYER_FLAGS_GHOST, PLAYER_FIELD_PLAYER_FLAGS, CMSG_REPOP_REQUEST,
    CMSG_AREA_SPIRIT_HEALER_QUEUE, SPELL_WAITING_FOR_RESURRECT, ALLIANCE,
    BG_CREATURE_ENTRY_A_SPIRITGUIDE, BG_CREATURE_ENTRY_H_SPIRITGUIDE };
constexpr float INTERACTION_DISTANCE = 5;
#define TC_LOG_DEBUG(...) ((void)0)
struct Event {};
struct Player;
struct Unit;
struct Creature;
struct Pet {};
struct Group;
struct WorldPacket {
    explicit WorldPacket(int) {}
    template<class T> void operator<<(T) {}
    void WriteBit(uint8) {}
    void FlushBits() {}
    void WriteByteSeq(uint8) {}
};
struct Session {
    Player* player = nullptr;
    int releases = 0, queues = 0;
    void HandleRepopRequestOpcode(WorldPacket&);
    void HandleAreaSpiritHealerQueueOpcode(WorldPacket&) { ++queues; }
};
struct WorldLocation {
    uint32 map = uint32(-1);
    float x = 0, y = 0, z = 0;
    WorldLocation() = default;
    WorldLocation(uint32 m, float a, float b, float c) : map(m), x(a), y(b), z(c) {}
    uint32 GetMapId() const { return map; }
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }
};
struct Map {
    bool dungeon = true;
    int allowAttempt = 1, collisionCalls = 0;
    bool IsDungeon() const { return dungeon; }
    bool IsRaid() const { return false; }
    bool CheckCollisionAndGetValidCoords(Player*, float, float, float, float&, float&, float&) {
        return ++collisionCalls >= allowAttempt;
    }
};
struct InstanceScript { bool fighting = false; bool IsEncounterInProgress() { return fighting; } } instance;
struct SpellInfo { bool positive = true; bool IsPositive() const { return positive; } } positive, negative{false};
struct Spell { SpellInfo* info = &positive; SpellInfo const* GetSpellInfo() { return info; } } healing, harmful{&negative};
struct Unit {
    ObjectGuid guid;
    Map* map = nullptr;
    bool alive = true, world = true, los = true, attackable = true, assistable = true;
    bool ghost = false, flight = false, interruptible = true;
    uint32 phase = 1;
    float x = 0, y = 0, z = 0, health = 100;
    std::array<Spell*, 2> spells{};
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return world; }
    Map* GetMap() const { return map; }
    uint32 GetMapId() const { return 1; }
    ObjectGuid GetGUID() const { return guid; }
    bool InSamePhase(Unit const* other) const { return phase == other->phase; }
    bool IsValidAttackTarget(Unit* other) { return other->attackable && InSamePhase(other); }
    bool IsValidAssistTarget(Unit* other) { return other->assistable && InSamePhase(other); }
    bool IsWithinLOSInMap(Unit* other) { return other->los; }
    float GetDistance(float a, float b, float c) const { return std::sqrt((x-a)*(x-a)+(y-b)*(y-b)+(z-c)*(z-c)); }
    float GetDistance(Unit* other) const { return GetDistance(other->x, other->y, other->z); }
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }
    float GetHealthPct() const { return health; }
    bool HasUnitState(int) { return flight; }
    bool HasFlag(int, int) { return ghost; }
    Spell* GetCurrentSpell(CurrentSpellTypes type) { return spells[type]; }
};
struct MotionMaster {
    int moves = 0;
    void Clear() {}
    void MovePoint(uint32, float, float, float, bool) { ++moves; }
};
struct Player : Unit {
    Group* group = nullptr;
    bool combat = false, bg = false, arena = false, tank = false, casting = false;
    bool vehicle = false, transport = false, waiting = false, moving = false;
    float orientation = 0;
    Creature* guide = nullptr;
    Session session;
    MotionMaster motion;
    Group* GetGroup() { return group; }
    bool IsInCombat() { return combat; }
    bool InBattleground() { return bg; }
    bool InArena() { return arena; }
    bool isDead() { return !alive; }
    bool HasPlayerFlag(int) { return ghost; }
    bool IsNonMeleeSpellCasted(bool, bool, bool) { return casting || spells[CURRENT_CHANNELED_SPELL]; }
    void* GetVehicle() { return vehicle ? this : nullptr; }
    void* GetTransport() { return transport ? this : nullptr; }
    float GetOrientation() { return orientation; }
    InstanceScript* GetInstanceScript() { return &instance; }
    Pet* GetPet() { return nullptr; }
    Session* GetSession() { session.player = this; return &session; }
    bool HasAura(int) { return waiting; }
    uint32 GetBGTeam() { return ALLIANCE; }
    Creature* FindNearestCreature(uint32, float, bool) { return guide; }
    bool IsWithinDistInMap(Unit* other, float distance) { return GetDistance(other) <= distance; }
    bool isMoving() { return moving; }
    void StopMoving() { moving = false; }
    MotionMaster* GetMotionMaster() { return &motion; }
};
void Session::HandleRepopRequestOpcode(WorldPacket&) { ++releases; player->ghost = true; }
struct Creature : Unit { bool IsSpiritService() { return true; } } guide;
struct GroupReference {
    Player* player;
    GroupReference* following = nullptr;
    Player* GetSource() { return player; }
    GroupReference* next() { return following; }
};
struct Group {
    std::vector<GroupReference> members;
    void Set(std::initializer_list<Player*> players) {
        members.clear();
        for (auto player : players) members.push_back({player});
        for (size_t i = 1; i < members.size(); ++i) members[i-1].following = &members[i];
    }
    GroupReference* GetFirstMember() { return members.empty() ? nullptr : &members[0]; }
};
struct Formation {
    std::string name = "chaos", target;
    static WorldLocation NullLocation;
    std::string getName() { return name; }
    std::string GetTargetName() { return target; }
    WorldLocation GetLocation() { return NullLocation; }
    float GetMaxDistance() { return 5; }
    static bool IsNullLocation(WorldLocation const& loc) { return loc.map == uint32(-1); }
};
WorldLocation Formation::NullLocation;
namespace PlayerBotSpec { bool IsTank(Player* player, bool) { return player->tank; } }
template<class T> struct Value { T value{}; T Get() { return value; } void Set(T v) { value = v; } };
struct Context {
    Value<GuidVector> attackers;
    Value<Unit*> target, master;
    Value<Formation*> formation;
    Value<uint32> deaths;
    Value<uint8> aoeCount;
    Value<float> distance;
    template<class T> Value<T>* GetValue(std::string const& key, std::string const& = "") {
        if constexpr (std::is_same_v<T, GuidVector>) return &attackers;
        else if constexpr (std::is_same_v<T, Unit*>) return key == "master target" ? &master : &target;
        else if constexpr (std::is_same_v<T, Formation*>) return &formation;
        else if constexpr (std::is_same_v<T, uint32>) return &deaths;
        else if constexpr (std::is_same_v<T, uint8>) return &aoeCount;
        else return &distance;
    }
};
#define AI_VALUE(T, key) context->GetValue<T>(key)->Get()
#define AI_VALUE2(T, key, qualifier) context->GetValue<T>(key, qualifier)->Get()
#define GET_PLAYERBOT_AI(player) false
struct PlayerbotAI {
    Context* context;
    Player* master = nullptr;
    int state = BOT_STATE_NON_COMBAT, delay = 0;
    bool moveFromGroup = false, realMaster = true;
    std::map<ObjectGuid, Unit*> units;
    std::string interrupt;
    Context* GetAiObjectContext() { return context; }
    Unit* GetUnit(ObjectGuid guid) { return units[guid]; }
    float GetRange(char const*) { return 30; }
    bool IsInterruptableSpellCasting(Unit* unit, std::string const& spell) {
        interrupt = spell; return !spell.empty() && unit->interruptible;
    }
    int GetState() { return state; }
    bool HasStrategy(char const*, int) { return moveFromGroup; }
    Player* GetGroupMaster() { return master; }
    bool HasActivePlayerMaster() { return realMaster; }
    bool IsRealPlayer() { return false; }
    void SetNextCheckDelay(int value) { delay = value; }
};
struct Config { float criticalHealth=20, lowHealth=40, mediumHealth=60, almostFullHealth=90,
    healDistance=40, sightDistance=60; } config;
auto sPlayerbotAIConfig = &config;
struct Facade { bool IsDistanceGreaterThan(float a, float b) { return a>b; } } facade;
auto sServerFacade = &facade;
struct AoeHealValue { Player* bot; std::string qualifier; uint8 Calculate(); };
struct EnemyHealerTargetValue { Player* bot; PlayerbotAI* botAI; std::string qualifier; Unit* Calculate(); };
struct AoeHealTrigger { Context* context; std::string type; int count=2; bool IsActive(); };
enum class MovementPriority { MOVEMENT_NORMAL, MOVEMENT_COMBAT };
struct FollowAction {
    Player* bot;
    PlayerbotAI* botAI;
    Context* context;
    int moves = 0, legacyFollows = 0;
    WorldLocation destination;
    bool normalOnly = false;
    Player* GetMaster() { return botAI->master; }
    bool UseGroupFollowFormation();
    bool CanMoveInGroupFormation();
    WorldLocation GetGroupFollowLocation();
    bool Execute(Event);
    bool isUseful();
    bool CanDeadFollow(Unit*);
    bool Follow(Unit*) { ++legacyFollows; return true; }
    bool MoveTo(uint32 map, float x, float y, float z, bool, bool, bool normal,
                bool, MovementPriority, bool) {
        ++moves; normalOnly=normal; destination={map,x,y,z}; return true;
    }
};
struct AutoReleaseSpiritAction {
    Player* bot;
    PlayerbotAI* botAI;
    Context* context;
    Player* GetMaster() { return botAI->master; }
    bool isUseful();
    bool Execute(Event);
};
'''

tests = r'''
void testValues()
{
    Map map, other;
    Player bot, friend1, friend2;
    bot.map = friend1.map = friend2.map = &map;
    bot.health = 10; friend1.health = 30; friend2.health = 55;
    Group group; group.Set({nullptr, &bot, &friend1, &friend2});
    AoeHealValue value{&bot, "medium"};
    assert(value.Calculate() == 0);
    bot.group = &group;
    for (auto [level, count] : std::array<std::pair<char const*, int>,4>{{
            {"critical",1}, {"low",2}, {"medium",3}, {"almost full",3}}}) {
        value.qualifier = level; assert(value.Calculate() == count);
    }
    value.qualifier = "medium";
    friend2.health = 60; assert(value.Calculate() == 2); // exclusive threshold
    friend2.health = 55;
    for (bool* flag : {&friend2.alive, &friend2.world, &friend2.assistable, &friend2.los}) {
        *flag = false; assert(value.Calculate() == 2); *flag = true;
    }
    friend2.map = &other; assert(value.Calculate() == 2); friend2.map = &map;
    friend2.phase = 2; assert(value.Calculate() == 2); friend2.phase = 1;
    friend2.z = 41; assert(value.Calculate() == 2); // other floor, not just 2D distance
    friend2.z = 40; assert(value.Calculate() == 3); friend2.z = 0;

    Context context;
    AoeHealTrigger trigger{&context, "medium"};
    context.aoeCount.value = 1; assert(!trigger.IsActive());
    context.aoeCount.value = 2; assert(trigger.IsActive());
    PlayerbotAI ai{&context};
    Unit enemy; enemy.map = &map; enemy.guid = {1}; enemy.spells[CURRENT_GENERIC_SPELL] = &healing;
    ai.units[{1}] = &enemy;
    context.attackers.value = {{999}, {1}};
    EnemyHealerTargetValue target{&bot, &ai, "kick"};
    assert(target.Calculate() == &enemy && ai.interrupt == "kick");
    context.target.value = &enemy; assert(!target.Calculate()); context.target.value = nullptr;
    for (bool* flag : {&enemy.alive, &enemy.world, &enemy.attackable, &enemy.los, &enemy.interruptible}) {
        *flag = false; assert(!target.Calculate()); *flag = true;
    }
    enemy.map = &other; assert(!target.Calculate()); enemy.map = &map;
    enemy.phase = 2; assert(!target.Calculate()); enemy.phase = 1;
    enemy.x = 31; assert(!target.Calculate()); enemy.x = 30; assert(target.Calculate()); enemy.x = 0;
    enemy.spells[CURRENT_GENERIC_SPELL] = &harmful; assert(!target.Calculate());
    enemy.spells[CURRENT_GENERIC_SPELL] = nullptr; assert(!target.Calculate());
    enemy.spells[CURRENT_CHANNELED_SPELL] = &healing; assert(target.Calculate());
    target.qualifier.clear(); assert(!target.Calculate());
}
void testFormation()
{
    Map map, other;
    Player bot, master, companion;
    bot.map = master.map = companion.map = &map;
    bot.guid = {30}; master.guid = {1}; companion.guid = {20};
    Group group; group.Set({&bot, nullptr, &master, &companion});
    bot.group = master.group = companion.group = &group;
    Context context; Formation formation; context.formation.value = &formation;
    PlayerbotAI ai{&context}; ai.master = &master;
    FollowAction action{&bot, &ai, &context};
    assert(action.UseGroupFollowFormation());
    auto loc = action.GetGroupFollowLocation();
    assert(loc.x == -4 && loc.y == 3); // second non-tank, ordered by GUID not roster
    group.Set({&companion, &master, &bot});
    auto reordered = action.GetGroupFollowLocation();
    assert(loc.x == reordered.x && loc.y == reordered.y);
    bot.tank = true; loc = action.GetGroupFollowLocation();
    assert(loc.x == 5 && loc.y == 0);
    master.orientation = float(M_PI_2); loc = action.GetGroupFollowLocation();
    assert(std::abs(loc.x) < 0.001 && std::abs(loc.y-5) < 0.001);
    master.orientation = 0;
    map.collisionCalls = 0; map.allowAttempt = 2;
    loc = action.GetGroupFollowLocation(); assert(loc.x == 2.5f && map.collisionCalls == 2);
    map.collisionCalls = 0; map.allowAttempt = 3;
    loc = action.GetGroupFollowLocation(); assert(loc.x == 1.25f && map.collisionCalls == 3);
    map.collisionCalls = 0; map.allowAttempt = 100;
    assert(Formation::IsNullLocation(action.GetGroupFollowLocation()));
    map.collisionCalls = 0; assert(!action.Execute({}) && !action.moves);
    map.collisionCalls = 0; assert(!action.isUseful());
    map.allowAttempt = 1;
    assert(action.isUseful() && action.Execute({}) && action.normalOnly && action.moves == 1);
    bot.x = 5; assert(!action.isUseful() && !action.Execute({}));
    bot.z = 3; assert(action.isUseful()); bot.x = bot.z = 0; // 3D arrival
    for (bool* flag : {&bot.casting, &bot.flight, &master.flight, &bot.vehicle, &master.vehicle,
                      &bot.transport, &master.transport, &ai.moveFromGroup}) {
        *flag = true;
        assert(!action.isUseful() && !action.Execute({}));
        *flag = false;
    }
    assert(action.moves == 1);
    for (bool* flag : {&bot.bg, &bot.combat, &master.combat}) {
        *flag = true; assert(!action.UseGroupFollowFormation()); *flag = false;
    }
    for (bool* flag : {&bot.alive, &master.alive, &bot.world, &master.world}) {
        *flag = false; assert(!action.UseGroupFollowFormation()); *flag = true;
    }
    master.map = &other; assert(!action.UseGroupFollowFormation()); master.map = &map;
    master.phase = 2; assert(!action.UseGroupFollowFormation()); master.phase = 1;
    master.group = nullptr; assert(!action.UseGroupFollowFormation()); master.group = &group;
    ai.state = BOT_STATE_COMBAT; assert(!action.UseGroupFollowFormation()); ai.state = BOT_STATE_NON_COMBAT;
    for (auto name : {"queue", "near", "line", "shield", "melee"}) {
        formation.name = name; assert(!action.UseGroupFollowFormation());
    }
    formation.target = "master target"; context.master.value = &master;
    assert(action.Execute({}) && action.legacyFollows == 1); // preserve explicit formations
    context.formation.value = nullptr; assert(!action.Execute({}) && !action.isUseful());
    for (std::size_t slot = 0; slot < 40; ++slot) {
        auto tank = GroupFollowFormation::GetOffset(true, slot);
        auto otherSlot = GroupFollowFormation::GetOffset(false, slot);
        assert(tank.forward > 0 && otherSlot.forward < 0);
        for (std::size_t previous = 0; previous < slot; ++previous) {
            auto previousSlot = GroupFollowFormation::GetOffset(true, previous);
            assert(tank.forward != previousSlot.forward || tank.sideways != previousSlot.sideways);
        }
    }
}
void testRelease()
{
    Map map, other;
    Player bot, master, survivor;
    bot.map = master.map = survivor.map = &map; bot.alive = false;
    Group group; group.Set({nullptr, &bot, &master, &survivor}); bot.group = &group;
    Context context; PlayerbotAI ai{&context}; ai.master = &master;
    AutoReleaseSpiritAction action{&bot, &ai, &context};
    assert(action.isUseful()); // alive master at entrance must not strand the dead bot
    instance.fighting = true;
    assert(!action.isUseful() && !action.Execute({}) && !bot.session.releases);
    instance.fighting = false; survivor.combat = true;
    assert(!action.isUseful() && !action.Execute({}));
    survivor.map = &other; assert(action.isUseful()); survivor.map = &map;
    survivor.world = false; assert(action.isUseful()); survivor.world = true;
    survivor.alive = false; assert(action.isUseful()); survivor.alive = true;
    survivor.combat = false;
    ai.master = nullptr;
    assert(action.Execute({}) && bot.session.releases == 1 && context.deaths.value == 1);
    assert(!action.isUseful() && !action.Execute({})); // already a ghost, no repeated release
    bot.ghost = false; bot.arena = true;
    assert(!action.isUseful() && !action.Execute({})); bot.arena = false;
    bot.alive = true; assert(!action.isUseful() && !action.Execute({})); bot.alive = false;
    assert(bot.session.releases == 1 && context.deaths.value == 1);

    // BG ghosts still reach native queue logic; no dungeon barrier or repeat repop.
    bot.bg = true; bot.ghost = true; bot.guide = &guide; instance.fighting = true;
    guide.map = &map;
    assert(action.isUseful() && action.Execute({}));
    assert(bot.session.queues == 1 && bot.session.releases == 1 && context.deaths.value == 1);
    bot.waiting = true; assert(action.Execute({}) && bot.session.queues == 1);
    bot.waiting = false; guide.x = 10;
    assert(action.Execute({}) && bot.motion.moves == 1 && bot.session.releases == 1);
    guide.x = 0; bot.ghost = false;
    assert(action.Execute({}) && bot.session.releases == 2 && bot.session.queues == 2);
    instance.fighting = false;
}
int main() { testValues(); testFormation(); testRelease(); }
'''

with tempfile.TemporaryDirectory(prefix="loa-party-backport-") as directory:
    cpp = Path(directory) / "regression.cpp"
    binary = Path(directory) / "regression"
    cpp.write_text(prefix + methods + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-I" + str(base / "value"),
                    str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="halt_on_error=1:detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1"))
print("PASS: healer Values/triggers, noncombat formation, dungeon release and BG ghost queue")
