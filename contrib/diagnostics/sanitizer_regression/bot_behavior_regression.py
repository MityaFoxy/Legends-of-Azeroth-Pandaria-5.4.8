#!/usr/bin/env python3
"""Exercise the actual opt-in Engine logging path with clock/logger doubles."""

import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
engine = (root / "modules/mod_playerbots/src/strategy/Engine.cpp").read_text()
header = (root / "modules/mod_playerbots/src/strategy/Engine.h").read_text()
start = engine.index("void Engine::LogAction(")
brace = engine.index("{", start)
end, depth = brace + 1, 1
while depth:
    depth += (engine[end] == "{") - (engine[end] == "}")
    end += 1
method = engine[start:end]
fields = header[
    header.index("    bool behaviorLogEnabled") : header.index(
        "    ActionExecutionListeners actionExecutionListeners"
    )
]
assert 'GetBoolDefault("AiPlayerbot.LogBehavior", false, true)' in engine
source = (
    r"""
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <string>
using uint32 = std::uint32_t;
uint32 clockNow = 0;
uint32 getMSTime() { return clockNow; }
uint32 getMSTimeDiff(uint32 before, uint32 after) { return after - before; }
int reports = 0;
uint32 recordedOk = 0, recordedFailed = 0;
std::string recordedAction;
#define TC_LOG_DEBUG(...) do { ++reports; recordedOk = behaviorActionsOk; recordedFailed = behaviorActionsFailed; recordedAction = lastBehaviorAction; } while (false)
struct Player {};
struct PlayerbotAI { Player bot; Player* GetBot() { return &bot; } };
struct Engine {
    PlayerbotAI* botAI;
    bool testMode = false;
    std::string lastAction;
"""
    + fields
    + r"""
    void LogAction(char const*, ...);
};
"""
    + method
    + r"""
int main() {
    PlayerbotAI ai;
    Engine engine; engine.botAI = &ai;
    engine.LogAction("A:%s - OK", "attack");
    engine.LogAction("--- AI Tick ---");
    assert(!reports && engine.lastBehaviorAction == "none");
    engine.behaviorLogEnabled = true;
    engine.LogAction("--- AI Tick ---");
    assert(reports == 1);
    engine.LogAction("A:%s - OK", "attack");
    engine.LogAction("A:%s - FAILED", "cast");
    engine.LogAction("A:%s - USELESS", "heal");
    assert(engine.behaviorActionsOk == 1 && engine.behaviorActionsFailed == 1);
    clockNow = 59999; engine.LogAction("--- AI Tick ---"); assert(reports == 1);
    clockNow = 60000; engine.LogAction("--- AI Tick ---");
    assert(reports == 2 && recordedOk == 1 && recordedFailed == 1);
    assert(recordedAction == "A:heal - USELESS");
    assert(!engine.behaviorActionsOk && !engine.behaviorActionsFailed);
    assert(engine.lastAction.empty()); // Diagnostics never changes the AI/test history.
    engine.LogAction("A:%s - OK", std::string(5000, 'x').c_str());
    assert(engine.lastBehaviorAction.size() == 511);
    Engine wrapped; wrapped.botAI = &ai; wrapped.behaviorLogEnabled = true;
    wrapped.behaviorLogInterval = 60;
    clockNow = UINT32_MAX - 10; wrapped.LogAction("--- AI Tick ---");
    int before = reports;
    clockNow = 48; wrapped.LogAction("--- AI Tick ---"); assert(reports == before);
    clockNow = 49; wrapped.LogAction("--- AI Tick ---"); assert(reports == before + 1);
}
"""
)
with tempfile.TemporaryDirectory(prefix="loa-bot-behavior-regression-") as directory:
    cpp = pathlib.Path(directory) / "regression.cpp"
    executable = pathlib.Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(cpp),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
print("Opt-in bounded bot behavior diagnostics regression passed")
