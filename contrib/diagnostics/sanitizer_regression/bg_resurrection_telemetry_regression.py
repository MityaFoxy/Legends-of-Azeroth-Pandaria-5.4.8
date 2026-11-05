#!/usr/bin/env python3
"""Execute the actual BG resurrection observer and feed its event to the soak gate.

World doubles validate observation boundaries, not native resurrection mechanics
(covered separately) or live graveyard navigation.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
root = Path(sys.argv[1]).resolve()
controller = (root / "modules/mod_playerbots/src/Manager/BattlegroundTestController.cpp").read_text()


def extract(signature):
    start = controller.index(signature)
    end = controller.index("{", start) + 1
    depth = 1
    while depth:
        depth += (controller[end] == "{") - (controller[end] == "}")
        end += 1
    return controller[start:end]


update = controller[controller.index("void BattlegroundTest::Update("):]
assert update.index("LogResurrection(bot, state, now);") < update.index("if (!bot->IsInWorld()")
assert update.count("LogResurrection(bot, state, now);") == 1

source = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
using uint32 = std::uint32_t;
enum class QueueReadinessIssue { None };
constexpr int BATTLEGROUND_AB = 3, STATUS_IN_PROGRESS = 3;
struct Map {};
struct Battleground {
    Map* map;
    uint32 instance = 11;
    int type = BATTLEGROUND_AB, status = STATUS_IN_PROGRESS;
    bool rated = false;
    Map* FindBgMap() { return map; }
    uint32 GetInstanceID() { return instance; }
    int GetTypeID() { return type; }
    int GetStatus() { return status; }
    bool IsRated() { return rated; }
};
struct Player {
    Battleground* bg;
    Map* map;
    uint32 instance = 11;
    bool alive = true, world = true, teleport = false;
    Battleground* GetBattleground() { return bg; }
    Map* GetMap() { return map; }
    uint32 GetInstanceId() { return instance; }
    bool IsInWorld() { return world; }
    bool IsBeingTeleported() { return teleport; }
    bool IsAlive() { return alive; }
};
'''
source += extract("struct State") + ";\n"
source += r'''
unsigned events = 0;
std::string emitted;
void LogState(Player* bot, State&, char const* phase, uint32) {
    assert(bot->IsAlive());
    assert(std::string(phase) == "resurrected");
    ++events;
    emitted += std::string("Bot=A GUID=7 phase=") + phase +
        " instance=11 alive=true matches=1 completed=0\n";
}
'''
source += extract("bool HasActiveBattlegroundMap(")
source += extract("void LogResurrection(")
source += r'''
int main() {
    Map map, otherMap;
    Battleground bg{&map};
    Player bot{&bg, &map};
    State state;
    auto tick = [&] { LogResurrection(&bot, state, 1000); };
    tick(); tick();
    assert(events == 0); // First alive observation is not a resurrection.
    for (unsigned i = 1; i <= 3; ++i) {
        bot.alive = false;
        tick(); tick();
        assert(events == i - 1);
        bot.alive = true;
        tick(); tick();
        assert(events == i); // One event per observed transition.
    }
    // Every invalid observation must discard the prior death, even if the bot
    // subsequently returns alive to exactly the same instance.
    for (int scenario = 0; scenario < 9; ++scenario) {
        bot.alive = false; tick();
        switch (scenario) {
            case 0: bot.bg = nullptr; break;
            case 1: bot.world = false; break;
            case 2: bot.teleport = true; break;
            case 3: bot.map = &otherMap; break;
            case 4: bg.map = nullptr; break;
            case 5: bg.type = 99; break;
            case 6: bg.rated = true; break;
            case 7: bg.status = 4; break; // Completion/exit auto-resurrection.
            case 8: bg.status = 2; break; // Preparation.
        }
        tick();
        bot = Player{&bg, &map}; bg = Battleground{&map};
        tick();
        assert(events == 3);
    }
    bot.alive = false; tick();
    bot.instance = bg.instance = 12; bot.alive = true; tick();
    assert(events == 3); // A new match cannot complete the previous death.
    bot.alive = false; tick();
    bot.instance = 13; tick(); // Mismatched map instance invalidates observation.
    bot.instance = 12; bot.alive = true; tick();
    assert(events == 3);
    bot.alive = false; tick();
    state = State{}; bot.alive = true; tick(); // Logout/recreated state.
    assert(events == 3);

    // Cross-component fixture: use the real observer's emitted event.
    emitted.clear(); state = State{};
    bot = Player{&bg, &map}; bg = Battleground{&map};
    bot.alive = false; tick(); bot.alive = true; tick();
    std::cout << emitted;
}
'''

spec = importlib.util.spec_from_file_location("soak", root / "contrib/diagnostics/sanitizer_soak.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)
with tempfile.TemporaryDirectory(prefix="loa-bg-resurrection-telemetry-") as directory:
    directory = Path(directory)
    cpp, exe = directory / "test.cpp", directory / "test"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1")
    event = subprocess.check_output([str(exe)], text=True, env=env)
    assert event.count("phase=resurrected") == 1
    log = directory / "BG.log"
    log.write_text("Bot=A GUID=7 phase=combat damage_done=42 matches=1 completed=0\n"
                   "Bot=A GUID=7 phase=dead matches=1 completed=0\n")
    telemetry = soak.BattlegroundTelemetry()
    assert not telemetry.sample(log)["cycle_verified"]
    with log.open("a") as out:
        out.write(event)
    state = telemetry.sample(log)
    assert state["resurrected_bots"] == 1 and not state["cycle_verified"]
    with log.open("a") as out:
        out.write("Bot=A GUID=7 phase=completed matches=1 completed=1\n"
                  "Bot=A GUID=7 phase=entered matches=2 completed=1\n")
    assert telemetry.sample(log)["cycle_verified"]
print("BG resurrection observation and soak gate regression passed")
