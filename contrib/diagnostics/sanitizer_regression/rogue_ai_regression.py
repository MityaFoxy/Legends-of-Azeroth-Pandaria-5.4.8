#!/usr/bin/env python3
"""Exercise native Rogue trigger factories, strategy handlers and cast predicates.

Compiles production triggers, strategy handlers, action queue and Engine dispatch
against bounded player/world doubles. Spell validation/effects, default actions,
listeners and time are doubles: this is not a live rotation, DBC or DPS test.
--verify-mutations checks that specific regressions fail their assertions.

Policy provenance: NotCronky d22152554ed1fb2062accbd589569a2d0f4da187,
adapted to our existing three/five-point strategies and native buff actions.
Local spell_rogue.cpp spells 5171/1766 and Player::GetComboTarget underpin the
contracts. Optional stealth/CC, poisons, legacy Hunger for Blood and the other
unregistered Rogue cooldown/debuff triggers remain outside this first slice.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]
base = root / "modules/mod_playerbots/src/strategy"
rogue = base / "Classes/rogue"


def block(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def without_includes(text):
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith('#include "'))


def clazz(text, name):
    return block(text, "class " + name + " :") + ";\n"


generic_h = (base / "triggers/GenericTriggers.h").read_text()
generic_cpp = (base / "triggers/GenericTriggers.cpp").read_text()
actions_h = (base / "actions/GenericSpellActions.h").read_text()
actions_cpp = (base / "actions/GenericSpellActions.cpp").read_text()
rogue_context = (rogue / "RogueAiObjectContext.cpp").read_text()
factory = clazz(rogue_context, "RogueTriggerFactoryInternal")
assert "triggerContexts.Add(new RogueTriggerFactoryInternal());" in rogue_context
stealth = block((rogue / "RogueActions.cpp").read_text(), "bool CastStealthAction::isPossible()")
slice_action = clazz((rogue / "RogueFinishingActions.h").read_text(), "CastSliceAndDiceAction")

prefix = r'''
#include <algorithm>
struct ActionExecutionTrace {
 explicit ActionExecutionTrace(bool = false) {}
 static bool Enabled() { return false; }
 static bool Fail(char const*) { return false; }
 template<class T> static void Target(T const*) {}
 static void Spell(unsigned, int = -1) {}
 bool GetRawResult() const { return false; }
 template<class... T> void Finish(T...) const {}
};
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <ctime>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using int32 = std::int32_t;
constexpr uint32 IN_MILLISECONDS = 1000;
constexpr int CURRENT_GENERIC_SPELL = 0;
#define TC_LOG_DEBUG(...) ((void)0)
class Action;
class Trigger;
struct WorldPacket {};
struct Event {
    bool active = false;
    Event() = default;
    explicit Event(std::string const&) : active(true) {}
    explicit operator bool() const { return active; }
};
uint32 getMSTime() { return 1000; }
struct Spell {};
struct Aura { int32 duration; int32 GetDuration() const { return duration; } };
struct Unit {
    bool alive = true, world = true, interruptible = false;
    float health = 100;
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return world; }
    uint32 GetMapId() const { return 1; }
    float GetHealthPct() const { return health; }
};
struct Player : Unit {
    Unit* comboTarget = nullptr;
    uint8 points = 0;
    bool combat = false;
    std::set<uint32> known, auras;
    Unit* GetComboTarget() const { return comboTarget; }
    uint8 GetComboPoints() const { return points; }
    bool HasSpell(uint32 id) const { return known.count(id); }
    bool IsInCombat() const { return combat; }
    bool IsMounted() const { return false; }
    void Dismount() {}
    Spell* GetCurrentSpell(int) { return nullptr; }
    bool IsWithinMeleeRange(Unit*) const { return false; }
};
template<class T> struct Value { T value{}; T Get() { return value; } };
struct Context {
    std::map<std::string, Value<Unit*>> targets;
    Value<bool> useful{true};
    std::string healerQualifier;
    int performanceStack = 0;
    std::function<Action*(std::string const&)> action;
    std::function<Trigger*(std::string const&)> trigger;
    Action* GetAction(std::string const& name) { return action(name); }
    Trigger* GetTrigger(std::string const& name) { return trigger(name); }
    template<class T> Value<T>* GetValue(std::string const& name, std::string const& qualifier = "") {
        if constexpr (std::is_same_v<T, bool>) return &useful;
        else {
            if (name == "enemy healer target") healerQualifier = qualifier;
            return &targets[name];
        }
    }
};
struct PlayerbotAI {
    Player* player;
    Context context;
    bool canCast = true;
    int castChecks = 0;
    Unit* checkedTarget = nullptr;
    std::vector<std::string> executions;
    std::map<std::pair<std::string, Unit*>, Aura*> auras;
    Player* GetBot() { return player; }
    Context* GetAiObjectContext() { return &context; }
    bool IsInVehicle(bool = false, bool = false, bool = false) { return false; }
    bool CanCastSpell(std::string const&, Unit* target) {
        ++castChecks; checkedTarget = target; return canCast;
    }
    bool IsInterruptableSpellCasting(Unit* target, std::string const& spell) {
        return spell == "kick" && target && target->interruptible;
    }
    Aura* GetAura(std::string const& spell, Unit* target, bool = false, bool = false) {
        return auras[{spell, target}];
    }
    bool HasAura(uint32 id, Unit*) { return player->auras.count(id); }
    float GetRange(std::string const&) { return 40; }
};
struct AiNamedObject {
    PlayerbotAI* botAI;
    Player* bot;
    Context* context;
    std::string name;
    AiNamedObject(PlayerbotAI* ai, std::string const& name)
        : botAI(ai), bot(ai->player), context(&ai->context), name(name) {}
    virtual ~AiNamedObject() = default;
    virtual std::string const getName() { return name; }
};
#define AI_VALUE(type, name) (context->GetValue<type>(name)->Get())
#define AI_VALUE2(type, name, qualifier) (context->GetValue<type>(name, qualifier)->Get())
'''

prefix += "\n".join(without_includes((base / file).read_text()) for file in (
    "Action.h", "Action.cpp", "Trigger.h", "Trigger.cpp"))
prefix += "\n".join(re.findall(r"^static float ACTION_.*;$",
                              (base / "Strategy.h").read_text(), re.M))
prefix += r'''
struct CastSpellAction : Action {
    std::string spell;
    float range = 0;
    CastSpellAction(PlayerbotAI* ai, std::string const& spell) : Action(ai, spell), spell(spell) {}
    std::string const GetTargetName() override { return "current target"; }
    bool isPossible() override;
    bool isUseful() override;
};
'''

generic = "\n".join([
    *(clazz(generic_h, name) for name in (
        "SpellTrigger", "BuffTrigger", "InterruptSpellTrigger", "InterruptEnemyHealerTrigger")),
    *(block(generic_cpp, sig) for sig in (
        "bool SpellTrigger::IsActive()", "bool BuffTrigger::IsActive()",
        "bool InterruptSpellTrigger::IsActive()",
        "Value<Unit*>* InterruptEnemyHealerTrigger::GetTargetValue()")),
    clazz(actions_h, "CastAuraSpellAction"), clazz(actions_h, "CastBuffSpellAction"),
    clazz(actions_h, "CastMeleeSpellAction"),
    *(block(actions_cpp, sig) for sig in (
        "bool CastSpellAction::isPossible()", "bool CastSpellAction::isUseful()",
        "bool CastAuraSpellAction::isUseful()", "bool CastMeleeSpellAction::isUseful()",
        "CastBuffSpellAction::CastBuffSpellAction(")),
    # Only used by the old-action mutation; the production constructor sets range.
    'CastMeleeSpellAction::CastMeleeSpellAction(PlayerbotAI* ai, std::string const spell) : CastSpellAction(ai, spell) {}',
    clazz((rogue / "RogueActions.h").read_text(), "CastStealthAction"),
    without_includes((base / "NamedObjectContext.h").read_text()),
    block((base / "NamedObjectContext.cpp").read_text(), "void Qualified::Qualify(int qual)"),
    without_includes((rogue / "RogueTriggers.h").read_text()),
    without_includes((rogue / "RogueTriggers.cpp").read_text()),
])

strategy_doubles = r'''
struct MeleeCombatStrategy {
    // Generic movement/target cleanup is covered by its own regression suites.
    void InitTriggers(std::vector<TriggerNode*>&) {}
};
struct DpsRogueStrategy : MeleeCombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct AssassinationRogueStrategy : MeleeCombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
'''

strategies = "\n".join([
    strategy_doubles,
    clazz((rogue / "DpsRogueStrategy.cpp").read_text(), "DpsRogueStrategyActionNodeFactory"),
    clazz((rogue / "AssassinationRogueStrategy.cpp").read_text(), "AssassinationRogueStrategyActionNodeFactory"),
    block((rogue / "DpsRogueStrategy.cpp").read_text(), "void DpsRogueStrategy::InitTriggers("),
    block((rogue / "AssassinationRogueStrategy.cpp").read_text(), "void AssassinationRogueStrategy::InitTriggers("),
])

engine_doubles = r'''
struct Config { uint32 iterationsPerTick = 10, expireActionTime = 3000; } config;
Config* sPlayerbotAIConfig = &config;
struct PerformanceMonitorOperation { void finish() {} };
struct Monitor {
    PerformanceMonitorOperation* start(int, std::string const&, int*) { return nullptr; }
} monitor;
Monitor* sPerformanceMonitor = &monitor;
constexpr int PERF_MON_ACTION = 0;
struct Multiplier {
    float GetValue(Action*) { return 1; }
    std::string getName() { return "unused"; }
};
'''
engine_doubles += "\n".join(without_includes((base / file).read_text())
                            for file in ("Queue.h", "Queue.cpp"))
engine_doubles += r'''
struct Engine {
    PlayerbotAI* botAI;
    Context* aiObjectContext;
    Queue queue;
    std::vector<TriggerNode*> triggers;
    std::vector<Multiplier*> multipliers;
    bool testMode = false;
    float lastRelevance = 0;
    std::function<ActionNode*(std::string const&)> makeNode;
    explicit Engine(PlayerbotAI* ai) : botAI(ai), aiObjectContext(&ai->context) {}
    ~Engine() {
        while (auto node = queue.Pop()) delete node;
        for (auto node : triggers) delete node;
    }
    ActionNode* CreateActionNode(std::string const name) {
        auto node = makeNode(name);
        return node ? node : new ActionNode(name);
    }
    void LogAction(char const*, ...) {}
    void PushDefaultActions() {} // Isolate handlers under test from idle/melee actions.
    bool ListenAndExecute(Action* action, Event event) { return action->Execute(event); }
    bool DoNextAction(Unit*, uint32 = 0, bool = false);
    bool MultiplyAndPush(NextAction**, float, bool, Event, char const*);
    void ProcessTriggers(bool);
    void PushAgain(ActionNode*, float, Event);
    Action* InitializeAction(ActionNode*);
};
'''
engine_source = (base / "Engine.cpp").read_text()
engine = engine_doubles + "\n".join(block(engine_source, signature) for signature in (
    "bool Engine::DoNextAction(", "bool Engine::MultiplyAndPush(",
    "void Engine::ProcessTriggers(", "void Engine::PushAgain(", "Action* Engine::InitializeAction("))

tests = r'''
void checkHandler(std::vector<TriggerNode*> const& nodes, std::string const& trigger,
                  std::string const& action, RogueTriggerFactoryInternal& factory, PlayerbotAI& ai) {
    auto resolved = factory.create(trigger, &ai);
    assert(resolved && "strategy trigger is unreachable");
    for (auto node : nodes) if (node->getName() == trigger) {
        node->setTrigger(resolved);
        auto handlers = node->getHandlers();
        bool found = false;
        for (size_t i = 0; handlers[i]; ++i)
            found |= handlers[i]->getName() == action;
        NextAction::destroy(handlers);
        if (found) return;
    }
    assert(false && "existing strategy handler lost");
}
void checkPredicates() {
    Player bot;
    Unit target, other;
    PlayerbotAI ai{&bot};
    ai.context.targets["self target"].value = &bot;
    ai.context.targets["current target"].value = &target;
    bot.comboTarget = &target;
    RogueTriggerFactoryInternal factory;
    auto three = factory.create("combo points 3 available", &ai);
    auto five = factory.create("combo points available", &ai);
    auto dying = factory.create("target with combo points almost dead", &ai);
    auto slice = factory.create("slice and dice", &ai);
    auto kick = factory.create("kick", &ai);
    auto healerKick = factory.create("kick on enemy healer", &ai);
    assert(three && five && dying && slice && kick && healerKick && "required Rogue trigger missing");
    for (uint8 points = 0; points <= 5; ++points) {
        bot.points = points;
        assert(three->IsActive() == (points >= 3) && "Assassination threshold must be three");
        assert(five->IsActive() == (points >= 5) && "DPS threshold must be five");
    }
    bot.known.insert(5171);
    assert(slice->IsActive());
    bot.comboTarget = &other;
    assert(!three->IsActive() && !five->IsActive() && !slice->IsActive() && "combo points belong to another target");
    bot.comboTarget = &target;
    ai.context.targets["current target"].value = nullptr;
    assert(!three->IsActive() && !five->IsActive() && !dying->IsActive() && !slice->IsActive());
    ai.context.targets["current target"].value = &target;
    target.alive = false;
    assert(!three->IsActive() && !five->IsActive() && !slice->IsActive() && "dead target cannot enable finishers");
    target.alive = true;
    bot.points = 1; target.health = 14;
    assert(dying->IsActive());
    target.health = 15;
    assert(!dying->IsActive());
    target.health = 14; bot.points = 0;
    assert(!dying->IsActive());
    bot.points = 1;
    bot.known.clear();
    assert(!slice->IsActive());
    bot.known.insert(5171);
    Aura buff{3000};
    ai.auras[{"slice and dice", &bot}] = &buff;
    CastSliceAndDiceAction sliceAction(&ai);
    assert(sliceAction.GetTarget() == &bot && "Slice and Dice must target self");
    assert(!slice->IsActive() && !sliceAction.isUseful());
    buff.duration = 2999;
    assert(slice->IsActive() && sliceAction.isUseful() && "Slice and Dice refresh must remain useful");
    buff.duration = 20000;
    assert(!slice->IsActive() && !sliceAction.isUseful());
    ai.auras[{"slice and dice", &bot}] = nullptr;
    assert(slice->IsActive() && sliceAction.isUseful());
    assert(sliceAction.isPossible() && ai.checkedTarget == &bot);
    bot.points = 0; // The same cached trigger must see a finisher consume the points.
    assert(!slice->IsActive() && !three->IsActive());
    assert(!kick->IsActive());
    target.interruptible = true;
    assert(kick->IsActive());
    assert(!healerKick->IsActive());
    ai.context.targets["enemy healer target"].value = &other;
    assert(healerKick->IsActive() && ai.context.healerQualifier == "kick");
    assert(healerKick->GetTarget() == &other && kick->GetTarget() == &target);
    // The healer selector's cast/LOS validation is tested in the party suite.
    CastStealthAction stealthAction(&ai);
    ai.canCast = false;
    assert(!stealthAction.isPossible() && ai.castChecks > 0 && "Stealth must obey core cast validation");
    ai.canCast = true;
    assert(stealthAction.isPossible() && ai.checkedTarget == &bot);
    for (uint32 flag : {23333u, 23335u, 34976u}) {
        bot.auras = {flag};
        int before = ai.castChecks;
        assert(!stealthAction.isPossible() && ai.castChecks == before);
    }
    bot.auras.clear();
    assert(stealthAction.isPossible());
    std::vector<TriggerNode*> nodes;
    DpsRogueStrategy dps;
    dps.InitTriggers(nodes);
    checkHandler(nodes, "combo points available", "rupture", factory, ai);
    checkHandler(nodes, "combo points available", "eviscerate", factory, ai);
    checkHandler(nodes, "slice and dice", "slice and dice", factory, ai);
    checkHandler(nodes, "target with combo points almost dead", "eviscerate", factory, ai);
    checkHandler(nodes, "kick", "kick", factory, ai);
    checkHandler(nodes, "kick on enemy healer", "kick on enemy healer", factory, ai);
    for (auto node : nodes) delete node;
    nodes.clear();
    AssassinationRogueStrategy assassination;
    assassination.InitTriggers(nodes);
    checkHandler(nodes, "combo points 3 available", "envenom", factory, ai);
    checkHandler(nodes, "slice and dice", "slice and dice", factory, ai);
    checkHandler(nodes, "kick", "kick", factory, ai);
    checkHandler(nodes, "kick on enemy healer", "kick on enemy healer", factory, ai);
    for (auto node : nodes) delete node;
    DpsRogueStrategyActionNodeFactory dpsFallbacks;
    AssassinationRogueStrategyActionNodeFactory assassinationFallbacks;
    std::unique_ptr<ActionNode> rupture(dpsFallbacks.create("rupture", &ai));
    std::unique_ptr<ActionNode> envenom(assassinationFallbacks.create("envenom", &ai));
    std::unique_ptr<ActionNode> mutilate(assassinationFallbacks.create("mutilate", &ai));
    Action action(&ai);
    for (auto node : {rupture.get(), envenom.get(), mutilate.get()}) node->setAction(&action);
    auto alternatives = rupture->getAlternatives();
    assert(alternatives[0]->getName() == "eviscerate");
    NextAction::destroy(alternatives);
    alternatives = envenom->getAlternatives();
    assert(alternatives[0]->getName() == "eviscerate");
    NextAction::destroy(alternatives);
    alternatives = mutilate->getAlternatives();
    assert(alternatives[0]->getName() == "sinister strike");
    NextAction::destroy(alternatives);
}
'''

combat_tests = r'''
// Observe execution while retaining each production action's predicates.
// Resource/aura changes below are explicit spell-effect doubles.
template<class Base> struct ObservedAction : Base {
    bool possible = true, outcome = true;
    std::function<void()> effect = [] {};
    template<class... Args> ObservedAction(PlayerbotAI* ai, Args&&... args)
        : Base(ai, std::forward<Args>(args)...) {}
    bool isPossible() override { return possible && Base::isPossible(); }
    bool Execute(Event) override {
        this->botAI->executions.push_back(this->getName());
        if (outcome) effect();
        return outcome;
    }
};
struct Combat {
    Player bot;
    Unit target, other;
    PlayerbotAI ai{&bot};
    RogueTriggerFactoryInternal triggers;
    DpsRogueStrategyActionNodeFactory dpsNodes;
    AssassinationRogueStrategyActionNodeFactory assassinationNodes;
    std::map<std::string, std::unique_ptr<Action>> actions;
    Engine engine{&ai};
    explicit Combat(bool assassination = true) {
        ai.context.targets["self target"].value = &bot;
        ai.context.targets["current target"].value = &target;
        bot.comboTarget = &target;
        ai.context.trigger = [this](std::string const& name) { return triggers.create(name, &ai); };
        ai.context.action = [this](std::string const& name) { return actions[name].get(); };
        engine.makeNode = [this, assassination](std::string const& name) {
            return assassination ? assassinationNodes.create(name, &ai) : dpsNodes.create(name, &ai);
        };
        if (assassination) AssassinationRogueStrategy().InitTriggers(engine.triggers);
        else DpsRogueStrategy().InitTriggers(engine.triggers);
    }
    template<class Base = Action, class... Args>
    ObservedAction<Base>& add(std::string const& key, Args&&... args) {
        auto value = std::make_unique<ObservedAction<Base>>(&ai, std::forward<Args>(args)...);
        auto& result = *value;
        actions[key] = std::move(value);
        return result;
    }
    bool tick() { return engine.DoNextAction(&target); }
    void expect(std::initializer_list<std::string> names) {
        assert(ai.executions == std::vector<std::string>(names) && "unexpected dispatch sequence");
        ai.executions.clear();
    }
};
void checkCombatSequences() {
    for (bool failedExecution : {false, true}) {
        Combat fight;
        auto& envenom = fight.add("envenom", "envenom");
        envenom.possible = failedExecution;
        envenom.outcome = false;
        auto& finisher = fight.add("eviscerate", "eviscerate");
        finisher.effect = [&] { fight.bot.points = 0; };
        for (uint8 points : {0, 1, 2}) {
            fight.bot.points = points;
            assert(!fight.tick() && "Assassination must wait for three combo points");
        }
        fight.bot.points = 3;
        fight.ai.context.targets["current target"].value = &fight.other;
        assert(!fight.tick() && "old target's combo points must not dispatch a finisher");
        fight.ai.context.targets["current target"].value = &fight.target;
        assert(fight.tick() && "unavailable envenom must execute its fallback");
        if (failedExecution) fight.expect({"envenom", "eviscerate"});
        else fight.expect({"eviscerate"});
        assert(fight.bot.points == 0 && !fight.tick() && "spent points must not retrigger a finisher");
        fight.expect({});
        // The same cached TriggerNode must become usable for a new combo target.
        fight.ai.context.targets["current target"].value = &fight.other;
        fight.bot.comboTarget = &fight.other;
        fight.bot.points = 3;
        assert(fight.tick());
    }
    {
        Combat fight;
        fight.add("mutilate", "mutilate").possible = false;
        fight.add("sinister strike", "sinister strike").effect = [&] { fight.bot.points = 1; };
        fight.engine.MultiplyAndPush(NextAction::array(0, new NextAction("mutilate", 20), nullptr),
                                     0, false, Event(), "test");
        assert(fight.tick() && "unavailable mutilate must dispatch sinister strike");
        fight.expect({"sinister strike"});
        assert(fight.bot.points == 1);
        fight.bot.known.insert(5171);
        Aura buff{20000};
        auto& slice = fight.add<CastSliceAndDiceAction>("slice and dice");
        slice.effect = [&] {
            fight.bot.points = 0;
            buff.duration = 20000;
            fight.ai.auras[{"slice and dice", &fight.bot}] = &buff;
        };
        assert(fight.tick() && "a built combo point must enable Slice and Dice");
        fight.expect({"slice and dice"});
        assert(fight.ai.checkedTarget == &fight.bot && !fight.tick());
        fight.bot.points = 1;
        buff.duration = 3000;
        assert(!fight.tick() && "Slice and Dice must not refresh at three seconds");
        buff.duration = 2999;
        assert(fight.tick() && "Slice and Dice must refresh below three seconds");
        fight.expect({"slice and dice"});
        assert(fight.bot.points == 0 && !fight.tick());
    }
    {
        Combat fight(false);
        fight.add("rupture", "rupture");
        fight.add("eviscerate", "eviscerate");
        fight.add("kick", "kick");
        fight.bot.points = 4;
        assert(!fight.tick() && "DPS must wait for five combo points");
        fight.bot.points = 5;
        fight.target.interruptible = true;
        assert(fight.tick());
        fight.expect({"kick"}); // Interruption has priority over a ready finisher.
        fight.target.interruptible = false;
        assert(fight.tick());
        fight.expect({"rupture"});
    }
    for (bool flagCarrier : {false, true}) {
        Combat fight(false);
        fight.add<CastStealthAction>("stealth");
        fight.add("sprint", "sprint");
        fight.add("reach melee", "reach melee");
        fight.ai.canCast = flagCarrier;
        if (flagCarrier) fight.bot.auras.insert(23333);
        // Queue the real enemy-out-of-melee strategy handlers. Its spatial
        // trigger belongs to the general movement suites, not this fixture.
        Trigger source(&fight.ai);
        for (auto node : fight.engine.triggers) if (node->getName() == "enemy out of melee") {
            node->setTrigger(&source);
            fight.engine.MultiplyAndPush(node->getHandlers(), 0, false, Event(), "test");
        }
        assert(fight.tick() && "rejected Stealth must leave another action executable");
        fight.expect({"sprint"});
    }
}
int main(int argc, char**) {
    if (argc == 1) checkPredicates();
    checkCombatSequences();
    std::cout << "PASS: Rogue predicates and native Engine combat sequences\n";
}
'''

environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                   UBSAN_OPTIONS="halt_on_error=1")
def replace_once(source, old, new):
    assert source.count(old) == 1, f"Mutation anchor changed: {old}"
    return source.replace(old, new, 1)


with tempfile.TemporaryDirectory(prefix="loa-rogue-ai-") as directory:
    def run(label, *, factory_body=factory, stealth_body=stealth, slice_body=slice_action,
            generic_body=generic, engine_body=engine, expected_assertion=None, combat_only=False):
        source = (prefix + generic_body + factory_body + stealth_body + slice_body + strategies
                  + engine_body + tests + combat_tests)
        binary = Path(directory) / label
        subprocess.run([compiler, "-x", "c++", "-std=c++20", "-g", "-O1",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-", "-o", str(binary)], input=source, text=True, check=True)
        command = [str(binary)] + (["--combat-only"] if combat_only else [])
        result = subprocess.run(command, env=environment, capture_output=True, text=True)
        if expected_assertion:
            assert (result.returncode != 0 and "Assertion" in result.stderr
                    and expected_assertion in result.stderr), result.stderr or f"Mutation survived: {label}"
            print(f"Mutation {label}: rejected by '{expected_assertion}'", flush=True)
        elif result.returncode:
            sys.stderr.write(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, [str(binary)])
        else:
            print(result.stdout, end="", flush=True)

    run("current")
    if "--verify-mutations" in sys.argv[3:]:
        missing = re.sub(r'^\s*creators\["slice and dice"\].*$', '', factory, flags=re.M)
        assert missing != factory
        run("missing-registration", factory_body=missing, expected_assertion="required Rogue trigger missing")
        old_stealth = replace_once(stealth, " &&\n        CastBuffSpellAction::isPossible()", "")
        run("stealth-without-core-check", stealth_body=old_stealth,
            expected_assertion="Stealth must obey core cast validation")
        old_slice = slice_action.replace("CastBuffSpellAction", "CastMeleeSpellAction").replace(
            ', false, 3 * IN_MILLISECONDS', '')
        assert old_slice != slice_action
        run("slice-targets-enemy", slice_body=old_slice, expected_assertion="Slice and Dice must target self")
        run("foreign-combo-points", generic_body=replace_once(generic, " || bot->GetComboTarget() != target", ""),
            expected_assertion="combo points belong to another target")
        run("dead-combo-target", generic_body=replace_once(generic, " || !target->IsAlive() || bot->GetComboTarget()",
                                                          " || bot->GetComboTarget()"),
            expected_assertion="dead target cannot enable finishers")
        run("wrong-assassination-threshold", factory_body=replace_once(factory,
            '"combo points 3 available", 3)', '"combo points 3 available", 5)'),
            expected_assertion="Assassination threshold must be three")
        run("spent-combo-points", generic_body=replace_once(generic, "return bot->GetComboPoints();",
            "static uint8 cached = 0; cached = std::max(cached, bot->GetComboPoints()); return cached;"),
            combat_only=True, expected_assertion="spent points must not retrigger a finisher")
        run("slice-never-refreshes", slice_body=replace_once(slice_action, "3 * IN_MILLISECONDS", "0"),
            expected_assertion="Slice and Dice refresh must remain useful")
        alternative = 'MultiplyAndPush(actionNode->getAlternatives(), relevance + 0.003f, false, event, "alt");'
        assert engine.count(alternative) == 2
        run("engine-drops-alternatives", engine_body=engine.replace(alternative, "(void)0;"),
            combat_only=True, expected_assertion="unavailable envenom must execute its fallback")
print("PASS: Rogue factories, live combo points, buff refresh, interrupts, Stealth and native Engine fallback dispatch")
