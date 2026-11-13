#!/usr/bin/env python3
"""Exercise production formation selection/dispatch with bounded world/nav doubles.

FleePosition is a boundary double: this verifies dispatch, failure propagation,
cast/movement guards and member isolation, not collision/path geometry.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
base = root / "modules/mod_playerbots/src/strategy/actions"
header = (base / "MovementActions.h").read_text()
source = (base / "MovementActions.cpp").read_text()


def block(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


code = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>
#include <map>
using uint32 = uint32_t;
uint32 clockNow = 10000;
uint32 getMSTime() { return clockNow; }
uint32 getMSTimeDiff(uint32 before, uint32 after) { return after - before; }
constexpr int CURRENT_CHANNELED_SPELL = 1;
struct Event {};
struct Position { float x = 0; };
struct Unit {};
struct Player;
struct Group {
    struct Slot { int guid; };
    using MemberSlotList = std::vector<Slot>;
    using member_citerator = MemberSlotList::const_iterator;
    MemberSlotList members;
    MemberSlotList const& GetMemberSlots() { return members; }
};
struct Player {
    Position pos;
    int map = 1, phase = 1;
    bool alive = true, inWorld = true, charmed = false, moving = false;
    bool channel = false, casting = false, vehicle = false, transport = false, flight = false;
    Group* group = nullptr;
    bool IsAlive() { return alive; }
    bool IsInWorld() { return inWorld; }
    int GetMap() { return map; }
    bool InSamePhase(Player* p) { return phase == p->phase; }
    bool IsCharmed() { return charmed; }
    float GetExactDist(Player* p) { return std::abs(pos.x - p->pos.x); }
    Position GetPosition() { return pos; }
    Group* GetGroup() { return group; }
    bool isMoving() { return moving; }
    bool IsNonMeleeSpellCasted(bool) { return casting || channel; }
    bool GetVehicle() { return vehicle; }
    bool GetTransport() { return transport; }
    bool IsInFlight() { return flight; }
    void* GetCurrentSpell(int) { return channel ? this : nullptr; }
};
std::map<int, Player*> players;
struct ObjectAccessor { static Player* FindPlayer(int guid) { return players[guid]; } };
struct ServerFacade { float GetDistance2d(Player* a, Player* b) { return a->GetExactDist(b); } } facade;
ServerFacade* sServerFacade = &facade;
struct Config { float sightDistance = 60; } config;
Config* sPlayerbotAIConfig = &config;
float disperseDistance = -1;
#define AI_VALUE(type, name) disperseDistance
struct PlayerbotAI { Player* bot; };
bool routeAccepted = true;
int routes = 0;
struct MovementAction {
    Player* bot;
    MovementAction(PlayerbotAI* ai, std::string) : bot(ai->bot) {}
    virtual bool isUseful() { return true; }
    virtual bool Execute(Event) { return false; }
    virtual ~MovementAction() = default;
    bool FleePosition(Position pos, float distance, uint32 interval) {
        assert(pos.x == 1 && distance == 3 && interval == 1000);
        ++routes;
        return routeAccepted;
    }
};
'''
for name in ("CombatFormationMoveAction", "TankFaceAction"):
    code += block(header, "class " + name + " :") + ";\n"
for signature in ("bool CombatFormationMoveAction::CanReposition()",
                  "bool CombatFormationMoveAction::isUseful()",
                  "bool CombatFormationMoveAction::Execute(Event event)",
                  "Player* CombatFormationMoveAction::NearestGroupMember(float dis)"):
    code += block(source, signature) + "\n"
code += r'''
// Tank-facing geometry is independently covered elsewhere; only its inherited
// eligibility contract is in this fixture.
bool TankFaceAction::Execute(Event) { return false; }
struct TestFormation : CombatFormationMoveAction {
    using CombatFormationMoveAction::CombatFormationMoveAction;
    using CombatFormationMoveAction::lastMoveTimer;
};
int main() {
    Player bot, member;
    member.pos.x = 1;
    Group group; group.members = {{1}, {2}, {3}};
    players = {{1, &bot}, {2, &member}, {3, nullptr}};
    bot.group = &group;
    PlayerbotAI ai{&bot};
    TestFormation action(&ai);
    TankFaceAction tank(&ai);
    assert(!action.isUseful() && !action.Execute({}) && routes == 0);
    assert(tank.isUseful()); // Disabled spread must not disable tank facing.
    disperseDistance = 3;
    for (bool* state : {&member.charmed, &bot.casting, &bot.channel, &bot.moving,
                        &bot.vehicle, &bot.transport, &bot.flight}) {
        *state = true;
        assert(!action.isUseful() && !action.Execute({}));
        *state = false;
    }
    member.alive = false; assert(!action.isUseful()); member.alive = true;
    member.inWorld = false; assert(!action.isUseful()); member.inWorld = true;
    member.map = 2; assert(!action.isUseful()); member.map = 1;
    member.phase = 2; assert(!action.isUseful()); member.phase = 1;
    member.pos.x = 10; assert(!action.isUseful()); member.pos.x = 1;
    bot.group = nullptr; assert(!action.isUseful()); bot.group = &group;
    routeAccepted = false;
    assert(action.isUseful() && !action.Execute({}) && action.lastMoveTimer == 0);
    routeAccepted = true;
    assert(action.Execute({}) && action.lastMoveTimer == clockNow && routes == 2);
    assert(!action.isUseful() && !action.Execute({}) && routes == 2);
    clockNow += 1000;
    assert(action.Execute({}) && routes == 3);
    action.lastMoveTimer = UINT32_MAX - 500;
    clockNow = 498; assert(!action.isUseful());
    clockNow = 499; assert(action.isUseful());
}
'''
with tempfile.TemporaryDirectory(prefix="loa-combat-formation-") as directory:
    cpp, exe = Path(directory) / "test.cpp", Path(directory) / "test"
    cpp.write_text(code)
    subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("Native combat formation dispatch and isolation regression passed")
