#!/usr/bin/env python3
"""Check real Hunter strategies, factories and pet/debuff predicates with doubles.

World/pet state and base spell execution are doubles; this verifies reachability,
conditions, aura ownership, priorities and targets, not native spell effects.
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
#include <set>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
using uint8=uint8_t; using uint32=uint32_t; using int32=int32_t;
struct Unit {
    virtual ~Unit() = default;
    bool alive = true;
    bool world = true;
    float health = 100;
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return world; }
    uint32 GetMapId() const { return 1; }
    uint32 GetHealth() const { return uint32(health); }
};
struct Pet : Unit {
    float GetHealthPct() const { return health; }
};
struct Spell {};
constexpr int CURRENT_GENERIC_SPELL = 0;
#define TC_LOG_DEBUG(...) ((void)0)
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
    bool IsMounted() const { return false; }
    bool IsInCombat() const { return false; }
    void Dismount() {}
    Spell* GetCurrentSpell(int) { return nullptr; }
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
    Value<bool> spellUseful{true};
    Value<float> groupDps{10};
    template<class T> Value<T>* GetValue(std::string const& name, std::string const& qualifier = "") {
        if constexpr (std::is_same_v<T, bool>) {
            if (name == "spell cast useful") return &spellUseful;
            assert(name == "mounted" && qualifier == "self target");
            return &mounted;
        } else if constexpr (std::is_same_v<T, float>) {
            assert(name == "estimated group dps");
            return &groupDps;
        } else return &targets[name];
    }
};
struct Aura {
    bool owned = true;
    int32 duration = 10000;
    int32 GetDuration() const { return duration; }
};
struct PlayerbotAI {
    Player* player;
    Context context;
    Pet* mended = nullptr;
    bool HasAura(std::string const& name, Unit* target) { return name == "mend pet" && target == mended; }
    std::map<std::pair<std::string, Unit*>, Aura> auras;
    std::set<std::string> known;
    bool castAllowed = true;
    Aura* GetAura(std::string const& name, Unit* target, bool own = false, bool = false) {
        auto i = auras.find({name, target});
        return i == auras.end() || (own && !i->second.owned) ? nullptr : &i->second;
    }
    bool IsInVehicle(bool = true, bool = true, bool = true) { return false; }
    bool CanCastSpell(std::string const& name, Unit* target) { return target && known.count(name) && castAllowed; }
    float GetRange(std::string const&) { return 40; }
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
generic_h = (base / 'triggers/GenericTriggers.h').read_text()
generic_cpp = (base / 'triggers/GenericTriggers.cpp').read_text()
for name in ('SpellTrigger', 'BuffTrigger', 'DebuffTrigger'):
    cpp += clazz(generic_h, name)
    cpp += block(generic_cpp, 'bool ' + name + '::IsActive()')
for name in ('DEBUFF_TRIGGER', 'DEBUFF_CHECKISOWNER_TRIGGER', 'DEBUFF_CHECKISOWNER_ACTION'):
    cpp += '\n' + re.search(r'^#define ' + name + r'\(.*?(?=\n\n)',
                     (base / 'AiObject.h').read_text(), re.M | re.S).group() + '\n'
actions_base_h = (base / 'actions/GenericSpellActions.h').read_text()
actions_base_cpp = (base / 'actions/GenericSpellActions.cpp').read_text()
for name in ('CastSpellAction', 'CastAuraSpellAction', 'CastBuffSpellAction', 'CastDebuffSpellAction'):
    cpp += clazz(actions_base_h, name)
for signature in ('CastSpellAction::CastSpellAction(', 'CastBuffSpellAction::CastBuffSpellAction(',
                  'bool CastSpellAction::isPossible()', 'bool CastSpellAction::isUseful()',
                  'bool CastAuraSpellAction::isUseful()', 'bool CastDebuffSpellAction::isUseful()',
                  'NextAction** CastSpellAction::getPrerequisites()'):
    cpp += block(actions_base_cpp, signature)
# Execution/world effects remain outside this fixture; tests invoke the real
# possibility/usefulness checks and verify delegation to the castability double.
cpp += 'bool CastSpellAction::Execute(Event) { return false; }\n'
actions_h = (hunter / 'HunterActions.h').read_text()
for name in ('CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction', 'CastBlackArrow', 'CastHuntersMarkAction'):
    cpp += clazz(actions_h, name)
cpp += re.search(r'^DEBUFF_CHECKISOWNER_ACTION\(CastSerpentStingAction,.*?;', actions_h, re.M).group() + '\n'
cpp += block((hunter / 'HunterActions.cpp').read_text(), 'bool CastHuntersMarkAction::isUseful()')
action_factory = clazz(context, 'HunterAiObjectContextInternal')
# The entire real factory is compiled. Unrelated spell implementations are doubles.
for name in sorted(set(re.findall(r'new (\w+)\(', action_factory)) -
                   {'CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction', 'CastBuffSpellAction', 'CastBlackArrow', 'CastHuntersMarkAction', 'CastSerpentStingAction'}):
    cpp += f'struct {name} : Action {{ explicit {name}(PlayerbotAI* ai) : Action(ai) {{}} }};\n'
cpp += action_factory
cpp += without_includes((hunter / 'HunterTriggers.h').read_text())
cpp += without_includes((hunter / 'HunterTriggers.cpp').read_text())
cpp += clazz(context, 'HunterTriggerFactoryInternal')
cpp += '\n'.join(re.findall(r'^static float ACTION_.*;$', (base / 'Strategy.h').read_text(), re.M))
cpp += r'''
struct CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct GenericHunterStrategy : CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct DpsHunterStrategy : GenericHunterStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct DpsHunterDebuffStrategy : CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct HunterPetStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
'''
cpp += block((hunter / 'GenericHunterStrategy.cpp').read_text(), 'void GenericHunterStrategy::InitTriggers(')
cpp += block((hunter / 'GenericHunterNonCombatStrategy.cpp').read_text(), 'void HunterPetStrategy::InitTriggers(')
cpp += block((hunter / 'DpsHunterStrategy.cpp').read_text(), 'void DpsHunterStrategy::InitTriggers(')
cpp += block((hunter / 'DpsHunterStrategy.cpp').read_text(), 'void DpsHunterDebuffStrategy::InitTriggers(')
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
        assert(handlers[0]->getName() == actionName && "Hunter handler changed");
        assert(handlers[0]->getRelevance() == relevance && "Hunter priority changed");
        auto action = actions.create(handlers[0]->getName(), &ai);
        assert(action && "Hunter action missing");
        if (actionName == "mend pet") {
            assert(dynamic_cast<CastMendPetAction*>(action));
            assert(action->GetTarget() == ai.player->pet && "mend must target pet");
        } else if (actionName == "revive pet") {
            assert(dynamic_cast<CastRevivePetAction*>(action));
            assert(action->GetTarget() == ai.player && "revive retains native self cast");
        } else if (actionName == "call pet 1") {
            assert(dynamic_cast<CastCallPetAction*>(action));
            assert(action->GetTarget() == ai.player && "call retains native self cast");
        } else {
            if (actionName == "serpent sting")
                assert(dynamic_cast<CastSerpentStingAction*>(action));
            else
                assert(actionName == "black arrow" ? dynamic_cast<CastBlackArrow*>(action) != nullptr :
                       dynamic_cast<CastHuntersMarkAction*>(action) != nullptr);
            assert(action->GetTarget() == ai.context.targets["current target"].value && "debuff must target current enemy");
        }
        NextAction::destroy(handlers);
        found = true;
    }
    assert(found && "existing Hunter strategy link missing");
}
void checkCombat() {
    Player bot; PlayerbotAI ai{&bot}; Unit enemy, other;
    ai.context.targets["self target"].value = &bot;
    HunterTriggerFactoryInternal triggers;
    HunterAiObjectContextInternal actions;
    auto arrow = triggers.create("black arrow", &ai);
    auto mark = triggers.create("hunter's mark", &ai);
    assert(arrow && mark && "combat triggers unreachable");
    assert(!arrow->IsActive() && !mark->IsActive());
    ai.context.targets["current target"].value = &enemy;
    assert(arrow->GetTarget() == &enemy && mark->GetTarget() == &enemy && "debuff trigger target changed");
    assert(arrow->IsActive() && mark->IsActive());
    enemy.alive = false;
    assert(!arrow->IsActive() && !mark->IsActive());
    enemy.alive = true; enemy.world = false;
    assert(!arrow->IsActive() && !mark->IsActive());
    enemy.world = true; enemy.health = 79;
    assert(!arrow->IsActive() && !mark->IsActive() && "short-lived target gate lost");
    enemy.health = 80;
    assert(arrow->IsActive() && mark->IsActive());
    ai.auras[{"black arrow", &enemy}] = Aura{false};
    assert(arrow->IsActive() && "another Hunter's Black Arrow must not block ours");
    ai.auras[{"black arrow", &enemy}].owned = true;
    assert(!arrow->IsActive() && "own Black Arrow must not be reapplied");
    ai.auras[{"hunter's mark", &enemy}] = Aura{false};
    assert(!mark->IsActive() && "shared Hunter's Mark must not be reapplied");
    ai.context.targets["current target"].value = &other;
    assert(arrow->IsActive() && mark->IsActive() && "cached trigger retained previous target");
    auto arrowAction = actions.create("black arrow", &ai);
    auto markAction = actions.create("hunter's mark", &ai);
    assert(arrowAction && markAction);
    assert(!arrowAction->isPossible() && !markAction->isPossible() && "unknown spells must stay unavailable");
    ai.known = {"black arrow", "hunter's mark"};
    assert(arrowAction->isPossible() && markAction->isPossible());
    assert(arrowAction->isUseful() && markAction->isUseful());
    ai.castAllowed = false;
    assert(!arrowAction->isPossible() && !markAction->isPossible() && "native cast rejection must be retained");
    ai.auras[{"black arrow", &other}] = Aura{true};
    ai.auras[{"hunter's mark", &other}] = Aura{false};
    assert(!arrowAction->isUseful() && !markAction->isUseful());
    std::vector<TriggerNode*> nodes;
    DpsHunterStrategy{}.InitTriggers(nodes);
    checkHandler(nodes, "black arrow", "black arrow", 19, arrow, actions, ai);
    checkHandler(nodes, "hunter's mark", "hunter's mark", 31, mark, actions, ai);
    for (auto node : nodes) delete node;
}
void checkSting() {
    Player bot; PlayerbotAI ai{&bot}; Unit enemy, other;
    HunterTriggerFactoryInternal triggers;
    HunterAiObjectContextInternal actions;
    auto sting = triggers.create("no stings", &ai);
    auto canonical = triggers.create("serpent sting", &ai);
    assert(sting && canonical && "Serpent Sting trigger aliases unreachable");
    assert(sting->getName() == "serpent sting" && canonical->getName() == "serpent sting");
    assert(!sting->IsActive());
    ai.context.targets["current target"].value = &enemy;
    assert(sting->GetTarget() == &enemy && sting->IsActive() && canonical->IsActive());
    auto action = actions.create("serpent sting", &ai);
    assert(action && action->GetTarget() == &enemy);
    assert(!action->isPossible());
    ai.known = {"serpent sting"};
    assert(action->isPossible() && action->isUseful());
    ai.auras[{"serpent sting", &enemy}] = Aura{false};
    assert(sting->IsActive() && canonical->IsActive() && action->isUseful() && "foreign Serpent Sting must not block ours");
    ai.auras[{"serpent sting", &enemy}].owned = true;
    assert(!sting->IsActive() && !canonical->IsActive() && !action->isUseful() && "own Serpent Sting must not be reapplied");
    ai.context.targets["current target"].value = &other;
    assert(sting->IsActive() && action->isUseful() && "Serpent Sting must follow target changes");
    other.alive = false;
    assert(!sting->IsActive() && !action->isUseful());
    other.alive = true; other.world = false;
    assert(!sting->IsActive() && !action->isUseful());
    other.world = true; other.health = 79;
    assert(!sting->IsActive() && "Serpent Sting lifetime gate lost");
    other.health = 80;
    assert(sting->IsActive());
    ai.castAllowed = false;
    assert(!action->isPossible());
    std::vector<TriggerNode*> nodes;
    DpsHunterDebuffStrategy{}.InitTriggers(nodes);
    checkHandler(nodes, "no stings", "serpent sting", 18, sting, actions, ai);
    for (auto node : nodes) delete node;
}
int main() {
    checkSting();
    checkCombat();
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
    std::cout << "PASS: native Hunter pet/debuff trigger/handler reachability, conditions and targets\n";
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
            ('black-arrow-registration', 'creators["black arrow"] = &HunterTriggerFactoryInternal', 'creators["missing black arrow"] = &HunterTriggerFactoryInternal', 'combat triggers unreachable'),
            ('mark-registration', 'creators["hunter\'s mark"] = &HunterTriggerFactoryInternal', 'creators["missing hunter\'s mark"] = &HunterTriggerFactoryInternal', 'combat triggers unreachable'),
            ('black-arrow-owner', 'DEBUFF_CHECKISOWNER_TRIGGER(BlackArrowTrigger, "black arrow")', 'DEBUFF_TRIGGER(BlackArrowTrigger, "black arrow")', "another Hunter's Black Arrow must not block ours"),
            ('mark-shared', 'DEBUFF_TRIGGER(HuntersMarkTrigger, "hunter\'s mark")', 'DEBUFF_CHECKISOWNER_TRIGGER(HuntersMarkTrigger, "hunter\'s mark")', "shared Hunter's Mark must not be reapplied"),
            ('sting-legacy-registration', 'creators["no stings"]', 'creators["missing no stings"]', 'Serpent Sting trigger aliases unreachable'),
            ('sting-canonical-registration', 'creators["serpent sting"] = &HunterTriggerFactoryInternal', 'creators["missing serpent sting"] = &HunterTriggerFactoryInternal', 'Serpent Sting trigger aliases unreachable'),
            ('sting-owner', 'DEBUFF_CHECKISOWNER_TRIGGER(SerpentStingTrigger, "serpent sting")', 'DEBUFF_TRIGGER(SerpentStingTrigger, "serpent sting")', 'foreign Serpent Sting must not block ours'),
        ]
        for name, before, after, assertion in mutations:
            assert cpp.count(before) == 1, name
            result = run(cpp.replace(before, after, 1))
            assert result.returncode and assertion in result.stderr, (name, result.stderr)
            print('Detected mutation:', name)
