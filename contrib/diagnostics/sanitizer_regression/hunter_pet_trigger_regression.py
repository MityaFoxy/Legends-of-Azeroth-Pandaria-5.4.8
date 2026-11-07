#!/usr/bin/env python3
"""Check real Hunter strategies, factories and pet predicates with bounded doubles.

World/pet state and base spell execution are doubles; this verifies reachability,
conditions, handler priorities and target names, not native healing/resurrection.
Comparison source: NotCronky 969150c0d398039e993a88913fe71a528b74dc41.
Keep local trigger names and configured MediumHealth instead of its fixed 50%.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
base = root / 'modules/mod_playerbots/src/strategy'
hunter = base / 'Classes/hunter'


def block(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def clazz(text, name):
    return block(text, 'class ' + name + ' :') + ';\n'


def without_includes(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#include "'))


context = (hunter / 'HunterAiObjectContext.cpp').read_text()
cpp = r'''
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
using uint8=uint8_t; using uint32=uint32_t; using int32=int32_t;
struct Unit { virtual ~Unit() = default; };
struct Pet : Unit {
    bool alive = true;
    float health = 100;
    bool IsAlive() const { return alive; }
    float GetHealthPct() const { return health; }
};
struct Guid { bool empty = true; bool IsEmpty() const { return empty; } };
struct Player : Unit {
    Pet* pet = nullptr;
    Unit* guardian = nullptr;
    Unit* controlled = nullptr;
    Guid minion;
    bool knowsCall = false;
    std::map<uint8, uint32> slots;
    Pet* GetPet() { return pet; }
    Guid GetMinionGUID() { return minion; }
    Unit* GetGuardianPet() { return guardian; }
    Unit* GetFirstControlled() { return controlled; }
    bool HasSpell(uint32 id) { assert(id == 883); return knowsCall; }
    uint32 GetPetIdBySlot(uint8 slot) { return slots[slot]; }
};
struct Event {
    bool active = false;
    Event() = default;
    explicit Event(std::string const&) : active(true) {}
    explicit operator bool() const { return active; }
};
struct WorldPacket {};
uint32 getMSTime() { return 10000; }
template<class T> struct Value { T value{}; T Get() { return value; } };
struct Context {
    std::map<std::string, Value<Unit*>> targets;
    Value<bool> mounted;
    template<class T> Value<T>* GetValue(std::string const& name, std::string const& qualifier = "") {
        if constexpr (std::is_same_v<T, bool>) {
            assert(name == "mounted" && qualifier == "self target");
            return &mounted;
        } else return &targets[name];
    }
};
struct PlayerbotAI {
    Player* player;
    Context context;
    Pet* mended = nullptr;
    bool HasAura(std::string const& name, Unit* target) { return name == "mend pet" && target == mended; }
};
struct AiNamedObject {
    PlayerbotAI* botAI; Player* bot; Context* context; std::string name;
    AiNamedObject(PlayerbotAI* ai, std::string const& name)
        : botAI(ai), bot(ai->player), context(&ai->context), name(name) {}
    virtual ~AiNamedObject() = default;
    virtual std::string const getName() { return name; }
};
struct Config { uint32 mediumHealth = 65; } config;
Config* sPlayerbotAIConfig = &config;
#define AI_VALUE(type, name) (context->GetValue<type>(name)->Get())
#define AI_VALUE2(type, name, qualifier) (context->GetValue<type>(name, qualifier)->Get())
'''
cpp += block((root / 'src/server/game/Entities/Pet/PetDefines.h').read_text(), 'enum PetSlot') + ';\n'
for file in ('Action.h', 'Action.cpp', 'Trigger.h', 'Trigger.cpp', 'NamedObjectContext.h'):
    cpp += without_includes((base / file).read_text()) + '\n'
cpp += block((base / 'NamedObjectContext.cpp').read_text(), 'void Qualified::Qualify(int qual)')
cpp += clazz((base / 'triggers/GenericTriggers.h').read_text(), 'NoPetTrigger')
cpp += block((base / 'triggers/GenericTriggers.cpp').read_text(), 'bool NoPetTrigger::IsActive()')
cpp += r'''
// Spell execution is outside this fixture. Real Hunter action wrappers below
// retain and expose the target name used by the native Action::GetTarget path.
struct CastSpellAction : Action {
    using Action::Action;
    std::string const GetTargetName() override { return "current target"; }
};
struct CastAuraSpellAction : CastSpellAction { using CastSpellAction::CastSpellAction; };
struct CastBuffSpellAction : CastSpellAction {
    using CastSpellAction::CastSpellAction;
    std::string const GetTargetName() override { return "self target"; }
};
'''
actions_h = (hunter / 'HunterActions.h').read_text()
for name in ('CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction'):
    cpp += clazz(actions_h, name)
action_factory = clazz(context, 'HunterAiObjectContextInternal')
# The entire real factory is compiled. Unrelated spell implementations are doubles.
for name in sorted(set(re.findall(r'new (\w+)\(', action_factory)) -
                   {'CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction', 'CastBuffSpellAction'}):
    cpp += f'struct {name} : Action {{ explicit {name}(PlayerbotAI* ai) : Action(ai) {{}} }};\n'
cpp += action_factory
cpp += without_includes((hunter / 'HunterTriggers.h').read_text())
cpp += without_includes((hunter / 'HunterTriggers.cpp').read_text())
cpp += clazz(context, 'HunterTriggerFactoryInternal')
cpp += '\n'.join(re.findall(r'^static float ACTION_.*;$', (base / 'Strategy.h').read_text(), re.M))
cpp += r'''
struct CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct GenericHunterStrategy : CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct HunterPetStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
'''
cpp += block((hunter / 'GenericHunterStrategy.cpp').read_text(), 'void GenericHunterStrategy::InitTriggers(')
cpp += block((hunter / 'GenericHunterNonCombatStrategy.cpp').read_text(), 'void HunterPetStrategy::InitTriggers(')
assert 'triggerContexts.Add(new HunterTriggerFactoryInternal());' in context
cpp += r'''
void checkHandler(std::vector<TriggerNode*>& nodes, std::string const& triggerName,
                  std::string const& actionName, float relevance, Trigger* trigger,
                  HunterAiObjectContextInternal& actions, PlayerbotAI& ai) {
    bool found = false;
    for (auto node : nodes) if (node->getName() == triggerName) {
        node->setTrigger(trigger);
        auto handlers = node->getHandlers();
        assert(handlers && handlers[0] && !handlers[1]);
        assert(handlers[0]->getName() == actionName && "pet handler changed");
        assert(handlers[0]->getRelevance() == relevance && "pet priority changed");
        auto action = actions.create(handlers[0]->getName(), &ai);
        assert(action && "pet action missing");
        if (actionName == "mend pet") {
            assert(dynamic_cast<CastMendPetAction*>(action));
            assert(action->GetTarget() == ai.player->pet && "mend must target pet");
        } else if (actionName == "revive pet") {
            assert(dynamic_cast<CastRevivePetAction*>(action));
            assert(action->GetTarget() == ai.player && "revive retains native self cast");
        } else {
            assert(dynamic_cast<CastCallPetAction*>(action));
            assert(action->GetTarget() == ai.player && "call retains native self cast");
        }
        NextAction::destroy(handlers);
        found = true;
    }
    assert(found && "existing pet strategy link missing");
}
int main() {
    Player bot; PlayerbotAI ai{&bot}; Pet pet, replacement;
    HunterTriggerFactoryInternal triggers;
    HunterAiObjectContextInternal actions;
    auto mend = triggers.create("hunters pet medium health", &ai);
    auto revive = triggers.create("hunters pet dead", &ai);
    assert(mend && revive && "pet triggers unreachable");
    auto call = triggers.create("hunter no pet", &ai);
    assert(call && "Hunter call trigger missing");
    assert(call->getName() == "hunter no pet");
    NoPetTrigger genericNoPet(&ai);
    assert(genericNoPet.IsActive() && !call->IsActive());
    bot.knowsCall = true;
    bot.slots[PET_SLOT_STABLE_FIRST] = 123;
    bot.slots[PET_SLOT_ACTIVE_FIRST + 1] = 124;
    assert(!call->IsActive() && "Call Pet 1 requires first active slot");
    bot.slots[PET_SLOT_ACTIVE_FIRST] = 125;
    bot.knowsCall = false;
    assert(!call->IsActive() && "Call Pet must be known");
    bot.knowsCall = true;
    assert(call->IsActive() && "owned first-slot pet must be callable");
    bot.minion.empty = false;
    assert(!call->IsActive() && "generic pet guards lost");
    bot.minion.empty = true;
    bot.guardian = &pet;
    assert(!call->IsActive());
    bot.guardian = nullptr;
    bot.controlled = &pet;
    assert(!call->IsActive());
    bot.controlled = nullptr;
    ai.context.mounted.value = true;
    assert(!call->IsActive());
    ai.context.mounted.value = false;
    ai.context.targets["pet target"].value = &pet;
    assert(!call->IsActive());
    pet.alive = false;
    assert(!call->IsActive() && "a loaded dead pet needs revival, not Call Pet");
    pet.alive = true;
    ai.context.targets["pet target"].value = nullptr;
    assert(call->IsActive());
    assert(triggers.create("hunters pet medium health", &ai) == mend);
    assert(!mend->IsActive() && !revive->IsActive() && "absent pet is not a dead pet");
    bot.pet = &pet;
    assert(!mend->IsActive() && !revive->IsActive());
    pet.health = 64.9f;
    assert(mend->IsActive() && !revive->IsActive() && "configured medium health ignored");
    assert(bool(mend->Check()));
    pet.health = 65;
    assert(!mend->IsActive() && "threshold must be strict");
    config.mediumHealth = 80;
    assert(mend->IsActive() && "health setting ignored");
    ai.mended = &pet;
    assert(!mend->IsActive() && "existing mend aura must be preserved");
    ai.mended = nullptr;
    pet.alive = false; pet.health = 0;
    assert(!mend->IsActive() && "dead pets must not be healed");
    assert(revive->IsActive() && bool(revive->Check()) && "dead pet must be revived");
    pet.alive = true;
    assert(!revive->IsActive() && "living pet must not be revived");
    bot.pet = &replacement;
    assert(!mend->IsActive() && !revive->IsActive() && "cached trigger retained old pet");
    replacement.health = 20;
    ai.mended = &pet;
    assert(mend->IsActive() && "old pet aura must not suppress replacement healing");
    ai.context.targets["self target"].value = &bot;
    ai.context.targets["pet target"].value = &replacement;
    std::vector<TriggerNode*> nodes;
    HunterPetStrategy{}.InitTriggers(nodes);
    checkHandler(nodes, "hunter no pet", "call pet 1", 60, call, actions, ai);
    checkHandler(nodes, "hunters pet medium health", "mend pet", 60, mend, actions, ai);
    checkHandler(nodes, "hunters pet dead", "revive pet", 60, revive, actions, ai);
    for (auto node : nodes) delete node;
    nodes.clear();
    GenericHunterStrategy{}.InitTriggers(nodes);
    checkHandler(nodes, "hunters pet medium health", "mend pet", ACTION_HIGH + 2, mend, actions, ai);
    for (auto node : nodes) delete node;
    bot.pet = nullptr;
    assert(!mend->IsActive() && !revive->IsActive());
    std::cout << "PASS: native Hunter pet trigger/handler reachability, conditions and targets\n";
}
'''
env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-hunter-triggers-') as directory:
    source, binary = Path(directory) / 'fixture.cpp', Path(directory) / 'fixture'

    def run(text):
        source.write_text(text)
        subprocess.run([compiler, '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', str(source), '-o', str(binary)], check=True)
        return subprocess.run([str(binary)], env=env, text=True, capture_output=True)

    result = run(cpp)
    print(result.stdout + result.stderr, end='')
    if result.returncode:
        raise SystemExit(1)
    if '--verify-mutations' in sys.argv:
        mutations = [
            ('registration', 'creators["hunters pet dead"]', 'creators["unregistered pet dead"]', 'pet triggers unreachable'),
            ('alive', 'pet && pet->IsAlive()', 'pet && !pet->IsAlive()', 'configured medium health ignored'),
            ('threshold', 'pet->GetHealthPct() < sPlayerbotAIConfig->mediumHealth', 'pet->GetHealthPct() < 50.0f', 'configured medium health ignored'),
            ('aura', '!botAI->HasAura("mend pet", pet)', 'true', 'existing mend aura must be preserved'),
            ('revive', 'return pet && !pet->IsAlive();', 'return pet && pet->IsAlive();', '!mend->IsActive() && !revive->IsActive()'),
            ('call-registration', 'creators["hunter no pet"]', 'creators["missing hunter no pet"]', 'Hunter call trigger missing'),
            ('call-slot', 'bot->GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST)', 'true', 'Call Pet 1 requires first active slot'),
            ('call-known', 'bot->HasSpell(883)', 'true', 'Call Pet must be known'),
            ('call-base', 'NoPetTrigger::IsActive() &&', 'true &&', 'generic pet guards lost'),
        ]
        for name, before, after, assertion in mutations:
            assert cpp.count(before) == 1, name
            result = run(cpp.replace(before, after, 1))
            assert result.returncode and assertion in result.stderr, (name, result.stderr)
            print('Detected mutation:', name)
