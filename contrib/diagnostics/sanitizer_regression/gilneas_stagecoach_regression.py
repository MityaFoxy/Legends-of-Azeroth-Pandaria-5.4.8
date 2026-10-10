#!/usr/bin/env python3
"""Exercise repeated Gilneas stagecoach harness creation under sanitizers."""

import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def method(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


gilneas_source = (
    root / "src/server/scripts/EasternKingdoms/zone_gilneas.cpp"
).read_text()
stagecoach_sql = (
    root / "sql/updates/world/2026_09_25_02_stagecoach_auto_movement_idempotent.sql"
).read_text()

# The moving harness is assembled by npc_stagecoach_harness from the clicked
# static carriage.  Database accessories for 43336 would create a second
# carriage and race the script for harness seats 0, 1 and 2.
accessory_section = stagecoach_sql.split(
    "-- ---------- vehicle_template_accessory ----------", 1
)[1].split("-- ---------- creature_equip_template", 1)[0]
accessory_values = accessory_section.split("VALUES", 1)[1]
assert not re.search(r"^\s*\(43336,", accessory_values, re.MULTILINE)

# Creature accessories need the generic 46598 ride aura, while the player must
# use only the quest's 72764 Board Vehicle spell. Casting both from one click
# races the carriage PassengerBoarded callback against harness assembly.
condition_section = stagecoach_sql.split(
    "-- ---------- conditions (separate accessory and player spellclicks) ----------", 1
)[1].split("-- ---------- vehicle_template_accessory ----------", 1)[0]
assert re.search(
    r"\(18,\s*44928,\s*46598,\s*0,\s*0,\s*31,\s*0,\s*3,\s*0,\s*0,\s*0,",
    condition_section,
)
assert re.search(
    r"\(18,\s*44928,\s*72764,\s*0,\s*0,\s*31,\s*0,\s*4,\s*0,\s*0,\s*0,",
    condition_section,
)
assert re.search(
    r"\(18,\s*44928,\s*72764,\s*0,\s*0,\s*47,\s*0,\s*24438,\s*10,\s*0,\s*0,",
    condition_section,
)
assert "43336, 30" not in condition_section

# Both phase copies of the first gate are opened by the script. The legacy
# door's old three-millisecond value rounded to zero in GetAutoCloseTime(),
# preventing the core from ever processing its runtime close deadline.
assert re.search(
    r"UPDATE\s+gameobject_template\s+SET\s+data2\s*=\s*3000\s+"
    r"WHERE\s+entry\s*=\s*196401\s+AND\s+type\s*=\s*0\s+AND\s+data2\s*=\s*3",
    stagecoach_sql,
    re.IGNORECASE,
)

# The summoned harness must bind to its actual summoner.  A proximity search
# can nondeterministically select the accessory clone instead of the carriage
# containing the player.
harness_begin = gilneas_source.index("struct npc_stagecoach_harness")
harness_end = gilneas_source.index("struct npc_ogre_ambusher_exodus", harness_begin)
harness_source = gilneas_source[harness_begin:harness_end]
assert "owner->ToCreature()" in harness_source
assert "FindNearestCreature(NPC_STAGECOACH_CARRIAGE" not in harness_source
is_summoned_by = method(harness_source, "void IsSummonedBy(Unit* owner) override")
assert is_summoned_by.index("passenger->ExitVehicle();") < is_summoned_by.index(
    "carriage->EnterVehicle(me, 2);"
)
assert "EVENT_REBOARD_CARRIAGE_PLAYER" in harness_source
carriage_begin = gilneas_source.index("class npc_stagecoach_carriage_exodus")
carriage_source = gilneas_source[carriage_begin:harness_begin]
assert "GetHomePosition()" in carriage_source
assert "PrepareStagecoachPassenger(passenger);" in carriage_source
assert "RemoveNpcPassengers();" in carriage_source
assert "SummonNpcPassengers();" in carriage_source
assert "NearTeleportTo(stagecoachSafeExitPosition" in carriage_source

waypoint_reached = method(harness_source, "void WaypointReached(uint32 waypointId, uint32 pathId) override")
waypoint_30 = waypoint_reached.split("case 30:", 1)[1]
assert "ACTION_STAGECOACH_FINISHED" in waypoint_30
assert "passenger->ExitVehicle()" not in waypoint_30

ogre_begin = gilneas_source.index("struct npc_ogre_ambusher_exodus")
ogre_end = gilneas_source.index("struct npc_koroth_the_hillbreaker", ogre_begin)
ogre_source = gilneas_source[ogre_begin:ogre_end]
assert "CastSpell" not in ogre_source

# The Greymane Manor gate has two overlapping phase copies. Open both by exact
# DB spawn so the harness cannot update a different copy than the player sees.
# Armed passengers must draw their loaded rifles instead of keeping them
# sheathed on their backs.
assert re.search(r"GO_FIRST_GATE\s*=\s*196864", gilneas_source)
assert re.search(r"GO_FIRST_GATE_SPAWN\s*=\s*166784", gilneas_source)
assert re.search(r"GO_FIRST_GATE_LEGACY_SPAWN\s*=\s*166771", gilneas_source)
open_first_gate = method(harness_source, "void OpenFirstGate()")
assert "OpenFirstGateBySpawn(GO_FIRST_GATE_SPAWN, GO_FIRST_GATE)" in open_first_gate
assert "OpenFirstGateBySpawn(GO_FIRST_GATE_LEGACY_SPAWN, GO_FIRST_GATE_LEGACY)" in open_first_gate
assert "GetGameObjectBySpawnId(spawnId)" in harness_source
assert "gate->SetGoState(GO_STATE_READY);" in harness_source
assert "gate->UseDoorOrButton(20, false, me);" in harness_source
assert re.search(r"case 1:\s*\{[^}]*OpenFirstGate\(\);", waypoint_reached, re.DOTALL)
assert "SetSheath(SHEATH_STATE_RANGED);" in gilneas_source
assert "(43907, 1, 0, 0, 2552)" in stagecoach_sql
assert "(51409, 1, 0, 0, 15460)" in stagecoach_sql

remove_npc_passengers = method(carriage_source, "void RemoveNpcPassengers()")
assert remove_npc_passengers.index("passenger->SetVisible(false);") < remove_npc_passengers.index(
    "passenger->ExitVehicle();"
)

passenger_boarded = method(
    gilneas_source,
    "void PassengerBoarded(Unit* passenger, int8 seatId, bool apply) override",
)
assert "!assemblingHarness && !journeyStarted" in passenger_boarded
recover_stagecoach = method(carriage_source, "void RecoverStagecoach(bool despawnHarness, bool finished = false)")

source = (
    r"""
#include <cassert>
#include <chrono>
#include <cstdint>

using int8 = std::int8_t;
using uint32 = std::uint32_t;
using namespace std::chrono_literals;

struct ObjectGuid
{
    std::uint64_t value = 0;
    bool IsEmpty() const { return value == 0; }
    void Clear() { value = 0; }
    bool operator==(ObjectGuid const& other) const { return value == other.value; }
};

struct Unit
{
    explicit Unit(bool player = false) : player(player) { }
    bool IsPlayer() const { return player; }
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return inWorld; }
    ObjectGuid GetGUID() const { return guid; }
    Unit* GetVehicleBase() const { return vehicleBase; }
    void ExitVehicle()
    {
        ++exitCalls;
        vehicleBase = nullptr;
    }
    void NearTeleportTo(float, float, float, float) { ++teleportCalls; }

    bool player;
    bool alive = true;
    bool inWorld = true;
    ObjectGuid guid{};
    Unit* vehicleBase = nullptr;
    int exitCalls = 0;
    int teleportCalls = 0;
};

struct Creature;

struct ObjectAccessor
{
    static Creature* GetCreature(Creature const& context, ObjectGuid guid);
    static Unit* GetUnit(Creature const& context, ObjectGuid guid);
};

struct Position
{
    float GetPositionX() const { return 10.0f; }
    float GetPositionY() const { return 20.0f; }
    float GetPositionZ() const { return 30.0f; }
    float GetOrientation() const { return 1.0f; }
};

struct Creature : Unit
{
    Creature() : Unit(false) { }

    Creature* GetVehicleCreatureBase() const { return static_cast<Creature*>(vehicleBase); }
    Creature* SummonCreature(uint32, float, float, float, float)
    {
        ++summonCalls;
        if (!summonResult)
            return nullptr;
        summonResult->inWorld = true;
        return summonResult;
    }
    float GetPositionX() const { return 1.0f; }
    float GetPositionY() const { return 2.0f; }
    float GetPositionZ() const { return 3.0f; }
    float GetOrientation() const { return 4.0f; }
    ObjectGuid GetGUID() const { return guid; }
    bool IsInWorld() const { return inWorld; }
    uint32 GetEntry() const { return entry; }
    void DespawnOrUnsummon()
    {
        ++despawnCalls;
        inWorld = false;
    }
    Position const& GetHomePosition() const { return home; }
    void NearTeleportTo(float, float, float, float) { ++teleportCalls; }

    Creature* summonResult = nullptr;
    Creature* lookupResult = nullptr;
    Unit* unitLookupResult = nullptr;
    Position home{};
    uint32 entry = 0;
    int summonCalls = 0;
    int despawnCalls = 0;
    int teleportCalls = 0;
    bool inWorld = false;
};

Creature* ObjectAccessor::GetCreature(Creature const& context, ObjectGuid guid)
{
    Creature* result = context.lookupResult;
    return result && result->GetGUID().value == guid.value ? result : nullptr;
}

Unit* ObjectAccessor::GetUnit(Creature const& context, ObjectGuid guid)
{
    Unit* result = context.unitLookupResult;
    return result && result->GetGUID().value == guid.value ? result : nullptr;
}

struct EventMap
{
    void ScheduleEvent(uint32, std::chrono::milliseconds) { ++scheduled; }
    void RescheduleEvent(uint32, std::chrono::milliseconds) { ++scheduled; }
    void Reset() { scheduled = 0; }
    int scheduled = 0;
};

struct BaseAI
{
    virtual ~BaseAI() = default;
    virtual void PassengerBoarded(Unit*, int8, bool) { }
};

constexpr uint32 NPC_HARNESS_SUMMONED = 43336;
constexpr uint32 EVENT_CARRIAGE_START_TIMEOUT = 1;
constexpr uint32 EVENT_CARRIAGE_RESUMMON_PASSENGERS = 3;
Position const stagecoachSafeExitPosition{};

struct StagecoachAI : BaseAI
{
    explicit StagecoachAI(Creature* creature) : me(creature) { }

    Creature* me;
    EventMap events;
    ObjectGuid harnessGuid{};
    ObjectGuid playerGuid{};
    bool assemblingHarness = false;
    bool journeyStarted = false;
    void SetStarterRigVisible(bool) { }
    void RemoveNpcPassengers() { }
    void SummonNpcPassengers() { }
"""
    + recover_stagecoach
    + r"""
"""
    + passenger_boarded
    + r"""
};

int main()
{
    Unit player(true);
    Unit npc(false);
    Creature carriage;
    Creature harness;
    carriage.entry = 44928;
    carriage.inWorld = true;
    player.guid.value = 100;
    harness.guid.value = 42;
    harness.entry = NPC_HARNESS_SUMMONED;
    StagecoachAI ai(&carriage);

    ai.PassengerBoarded(&npc, 1, true);
    ai.PassengerBoarded(&player, 0, true);
    ai.PassengerBoarded(&player, 1, false);
    assert(carriage.summonCalls == 0);

    carriage.unitLookupResult = &player;
    player.vehicleBase = &carriage;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 1);
    assert(ai.events.scheduled == 0);
    assert(player.exitCalls == 1);

    carriage.summonResult = &harness;
    carriage.lookupResult = &harness;
    player.vehicleBase = &carriage;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 2);
    assert(ai.events.scheduled == 2);
    assert(ai.assemblingHarness);

    ai.PassengerBoarded(&player, 1, false);
    assert(ai.events.scheduled == 2);

    carriage.vehicleBase = &harness;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 2);

    harness.inWorld = false;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 3);
    assert(harness.despawnCalls >= 1);

    player.vehicleBase = &carriage;
    ai.playerGuid = player.guid;
    ai.RecoverStagecoach(false, true);
    assert(player.exitCalls >= 2);
    assert(player.teleportCalls == 1);
}
"""
)

with tempfile.TemporaryDirectory(prefix="loa-gilneas-stagecoach-regression-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run(
        [
            compiler,
            "-x",
            "c++",
            "-std=c++20",
            "-g",
            "-O1",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-",
            "-o",
            str(binary),
        ],
        input=source,
        text=True,
        check=True,
    )
    subprocess.run([str(binary)], check=True)

print("Gilneas stagecoach repeated-harness regression: PASS")
