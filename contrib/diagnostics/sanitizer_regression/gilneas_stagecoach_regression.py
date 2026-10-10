#!/usr/bin/env python3
"""Exercise repeated Gilneas stagecoach harness creation under sanitizers."""

import pathlib
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
passenger_boarded = method(
    gilneas_source,
    "void PassengerBoarded(Unit* passenger, int8 seatId, bool apply) override",
)

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
};

struct Unit
{
    explicit Unit(bool player = false) : player(player) { }
    bool IsPlayer() const { return player; }
    bool player;
};

struct Creature;

struct ObjectAccessor
{
    static Creature* GetCreature(Creature const& context, ObjectGuid guid);
};

struct Creature : Unit
{
    Creature() : Unit(false) { }

    Creature* GetVehicleCreatureBase() const { return vehicleBase; }
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

    Creature* vehicleBase = nullptr;
    Creature* summonResult = nullptr;
    Creature* lookupResult = nullptr;
    ObjectGuid guid{};
    int summonCalls = 0;
    bool inWorld = false;
};

Creature* ObjectAccessor::GetCreature(Creature const& context, ObjectGuid guid)
{
    Creature* result = context.lookupResult;
    return result && result->GetGUID().value == guid.value ? result : nullptr;
}

struct EventMap
{
    void ScheduleEvent(uint32, std::chrono::milliseconds) { ++scheduled; }
    int scheduled = 0;
};

struct BaseAI
{
    virtual ~BaseAI() = default;
    virtual void PassengerBoarded(Unit*, int8, bool) { }
};

constexpr uint32 NPC_HARNESS_SUMMONED = 43336;
constexpr uint32 EVENT_CARRIAGE_RESUMMON_PASSENGERS = 3;

struct StagecoachAI : BaseAI
{
    explicit StagecoachAI(Creature* creature) : me(creature) { }

    Creature* me;
    EventMap events;
    bool harnessSummoned = false;
    ObjectGuid harnessGuid{};
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
    harness.guid.value = 42;
    StagecoachAI ai(&carriage);

    ai.PassengerBoarded(&npc, 1, true);
    ai.PassengerBoarded(&player, 0, true);
    ai.PassengerBoarded(&player, 1, false);
    assert(carriage.summonCalls == 0);

    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 1);
    assert(ai.events.scheduled == 0);

    carriage.summonResult = &harness;
    carriage.lookupResult = &harness;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 2);
    assert(ai.events.scheduled == 1);

    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 2);

    harness.inWorld = false;
    ai.PassengerBoarded(&player, 1, true);
    assert(carriage.summonCalls == 3);
    assert(ai.events.scheduled == 2);
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
