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
using ObjectGuid=uint32; using GuidVector=std::vector<ObjectGuid>;
enum AuraType { SPELL_AURA_MOD_CONFUSE, SPELL_AURA_MOD_FEAR, SPELL_AURA_MOD_FEAR_2,
    SPELL_AURA_MOD_STUN, SPELL_AURA_TRANSFORM, SPELL_AURA_MOD_ROOT };
constexpr int SPELL_ATTR0_BREAKABLE_BY_DAMAGE=1, AURA_INTERRUPT_FLAG_TAKE_DAMAGE=2;
constexpr uint32 TAKEN_HIT_PROC_FLAG_MASK=4;
constexpr int CURRENT_CHANNELED_SPELL=1;
struct SpellInfo {
    uint32 Id=0, ProcFlags=0, ProcCharges=0;
    bool breakable=false, interrupt=false;
    bool HasAttribute(int) const { return breakable; }
    bool HasAuraInterruptFlag(int) const { return interrupt; }
};
struct AuraEffect { SpellInfo info; SpellInfo const* GetSpellInfo() const { return &info; } };
struct Spell { SpellInfo info; SpellInfo const* GetSpellInfo() const { return &info; } };
struct Unit {
    virtual ~Unit() = default;
    bool alive = true;
    bool world = true;
    float health = 100;
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return world; }
    uint32 GetMapId() const { return 1; }
    uint32 GetHealth() const { return uint32(health); }
    uint32 instance=1, phase=1;
    bool valid=true, los=true, scatter=false;
    float distance=10;
    using AuraEffectList=std::vector<AuraEffect*>;
    std::map<AuraType, AuraEffectList> cc;
    AuraEffectList const& GetAuraEffectsByType(AuraType type) const {
        static const AuraEffectList empty;
        auto i=cc.find(type); return i==cc.end() ? empty : i->second;
    }
    Spell* GetCurrentSpell(int) { return nullptr; }
    bool HasAura(uint32 id) const { assert(id==19503); return scatter; }
    bool HasBreakableByDamageAuraType(AuraType type, uint32 excludeAura=0) const;
    bool HasBreakableByDamageCrowdControlAura(Unit* excludeCasterChannel=nullptr) const;
};
struct Pet : Unit {
    float GetHealthPct() const { return health; }
};
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
    bool IsInMap(Unit* other) const { return world && other->world && instance==other->instance; }
    bool InSamePhase(Unit* other) const { return phase & other->phase; }
    bool IsWithinCombatRange(Unit* other, float range) const { return other->distance <= range; }
};
struct AttackersValue {
    static bool IsValidTarget(Unit* target, Player*) { return target->alive && target->valid && target->los; }
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
    Value<GuidVector> attackers;
    template<class T> Value<T>* GetValue(std::string const& name, std::string const& qualifier = "") {
        if constexpr (std::is_same_v<T, bool>) {
            if (name == "spell cast useful") return &spellUseful;
            assert(name == "mounted" && qualifier == "self target");
            return &mounted;
        } else if constexpr (std::is_same_v<T, float>) {
            assert(name == "estimated group dps");
            return &groupDps;
        } else if constexpr (std::is_same_v<T, GuidVector>) {
            assert(name=="attackers"); return &attackers;
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
    bool HasAura(std::string const& name, Unit* target, bool = false, bool own = false) {
        return name=="mend pet" ? target==mended : GetAura(name,target,own)!=nullptr;
    }
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
    Player* GetBot() { return player; }
    Context* GetAiObjectContext() { return &context; }
    std::map<ObjectGuid, Unit*> units;
    Unit* GetUnit(ObjectGuid id) { return units[id]; }
    Unit* castTarget=nullptr; uint32 casts=0;
    bool CastSpell(std::string const& name, Unit* target) {
        assert(target && "must not cast at a missing target"); ++casts; castTarget=target;
        return CanCastSpell(name,target);
    }
};
Unit* SelectSerpentStingAttacker(PlayerbotAI* botAI);
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
unit_cpp = (root / 'src/server/game/Entities/Unit/Unit.cpp').read_text()
cpp += block(unit_cpp, 'bool Unit::HasBreakableByDamageAuraType(')
cpp += block(unit_cpp, 'bool Unit::HasBreakableByDamageCrowdControlAura(')
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
cpp += clazz(generic_h, 'DebuffOnAttackerTrigger')
cpp += block(generic_cpp, 'Value<Unit*>* DebuffOnAttackerTrigger::GetTargetValue()')
for name in ('DEBUFF_TRIGGER', 'DEBUFF_CHECKISOWNER_TRIGGER', 'DEBUFF_CHECKISOWNER_ACTION'):
    cpp += '\n' + re.search(r'^#define ' + name + r'\(.*?(?=\n\n)',
                     (base / 'AiObject.h').read_text(), re.M | re.S).group() + '\n'
actions_base_h = (base / 'actions/GenericSpellActions.h').read_text()
actions_base_cpp = (base / 'actions/GenericSpellActions.cpp').read_text()
for name in ('CastSpellAction', 'CastAuraSpellAction', 'CastBuffSpellAction', 'CastDebuffSpellAction', 'CastDebuffSpellOnAttackerAction'):
    cpp += clazz(actions_base_h, name)
for signature in ('CastSpellAction::CastSpellAction(', 'CastBuffSpellAction::CastBuffSpellAction(',
                  'bool CastSpellAction::isPossible()', 'bool CastSpellAction::isUseful()',
                  'bool CastAuraSpellAction::isUseful()', 'bool CastDebuffSpellAction::isUseful()',
                  'NextAction** CastSpellAction::getPrerequisites()'):
    cpp += block(actions_base_cpp, signature)
cpp += block(actions_base_cpp, 'Value<Unit*>* CastDebuffSpellOnAttackerAction::GetTargetValue()')
# Execution/world effects remain outside this fixture; tests invoke the real
# possibility/usefulness checks and verify delegation to the castability double.
cpp += 'bool CastSpellAction::Execute(Event) { return false; }\n'
actions_h = (hunter / 'HunterActions.h').read_text()
for name in ('CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction', 'CastBlackArrow', 'CastHuntersMarkAction', 'CastSerpentStingOnAttackerAction'):
    cpp += clazz(actions_h, name)
cpp += re.search(r'^DEBUFF_CHECKISOWNER_ACTION\(CastSerpentStingAction,.*?;', actions_h, re.M).group() + '\n'
cpp += block((hunter / 'HunterActions.cpp').read_text(), 'bool CastHuntersMarkAction::isUseful()')
actions_cpp = (hunter / 'HunterActions.cpp').read_text()
# The old source still compiles for the before-fix reachability reproduction.
if 'Unit* SelectSerpentStingAttacker(' in actions_cpp:
    for signature in ('Unit* SelectSerpentStingAttacker(',
                      'Unit* CastSerpentStingOnAttackerAction::GetTarget()',
                      'bool CastSerpentStingOnAttackerAction::Execute('):
        cpp += block(actions_cpp, signature)
action_factory = clazz(context, 'HunterAiObjectContextInternal')
# The entire real factory is compiled. Unrelated spell implementations are doubles.
for name in sorted(set(re.findall(r'new (\w+)\(', action_factory)) -
                   {'CastMendPetAction', 'CastRevivePetAction', 'CastCallPetAction', 'CastBuffSpellAction', 'CastBlackArrow', 'CastHuntersMarkAction', 'CastSerpentStingAction', 'CastSerpentStingOnAttackerAction'}):
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
struct DpsAoeHunterStrategy : CombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct HunterPetStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
'''
cpp += block((hunter / 'GenericHunterStrategy.cpp').read_text(), 'void GenericHunterStrategy::InitTriggers(')
cpp += block((hunter / 'GenericHunterNonCombatStrategy.cpp').read_text(), 'void HunterPetStrategy::InitTriggers(')
cpp += block((hunter / 'DpsHunterStrategy.cpp').read_text(), 'void DpsHunterStrategy::InitTriggers(')
cpp += block((hunter / 'DpsHunterStrategy.cpp').read_text(), 'void DpsHunterDebuffStrategy::InitTriggers(')
cpp += block((hunter / 'DpsHunterStrategy.cpp').read_text(), 'void DpsAoeHunterStrategy::InitTriggers(')
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
        } else if (actionName == "serpent sting on attacker") {
            assert(dynamic_cast<CastSerpentStingOnAttackerAction*>(action));
            assert(action->GetTarget()==trigger->GetTarget() && "attacker target disagreement");
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
void checkStingAttacker() {
    Player bot; PlayerbotAI ai{&bot}; Unit current, high, low;
    ai.context.targets["current target"].value=&current;
    ai.known={"serpent sting"};
    ai.units={{1,&current},{2,&high},{3,&low}};
    ai.context.attackers.value={0,1,2,3};
    current.health=1000; high.health=300; low.health=100;
    HunterTriggerFactoryInternal triggers; HunterAiObjectContextInternal actions;
    auto trigger=triggers.create("serpent sting on attacker", &ai);
    auto action=actions.create("serpent sting on attacker", &ai);
    assert(trigger && action && "attacker Serpent Sting unreachable");
    assert(trigger->GetTarget()==&high && action->GetTarget()==&high && "must select healthiest secondary attacker");
    assert(trigger->IsActive() && action->isUseful() && action->isPossible());
    AuraEffect control; control.info.breakable=true;
    for (auto type : {SPELL_AURA_MOD_CONFUSE, SPELL_AURA_MOD_FEAR, SPELL_AURA_MOD_FEAR_2,
                      SPELL_AURA_MOD_STUN, SPELL_AURA_TRANSFORM, SPELL_AURA_MOD_ROOT}) {
        high.cc[type]={&control};
        assert(trigger->GetTarget()==&low && action->GetTarget()==&low && "breakable CC must not attract Serpent Sting");
        high.cc.clear();
    }
    high.scatter=true;
    assert(trigger->GetTarget()==&low && "Scatter Shot special case lost");
    high.scatter=false;
    control.info.breakable=false; control.info.interrupt=true;
    high.cc[SPELL_AURA_MOD_CONFUSE]={&control};
    assert(trigger->GetTarget()==&low);
    control.info.interrupt=false; control.info.ProcFlags=TAKEN_HIT_PROC_FLAG_MASK; control.info.ProcCharges=1;
    assert(trigger->GetTarget()==&low);
    control.info.ProcFlags=0; control.info.ProcCharges=0;
    assert(trigger->GetTarget()==&high && "nonbreakable control must remain attackable");
    high.cc.clear();
    ai.auras[{"serpent sting",&high}]=Aura{false};
    assert(trigger->GetTarget()==&high && "foreign attacker aura must not block ours");
    ai.auras[{"serpent sting",&high}].owned=true;
    assert(trigger->GetTarget()==&low && "own attacker aura must not be reapplied");
    ai.auras.clear();
    for (bool* flag : {&high.alive,&high.world,&high.valid,&high.los}) {
        *flag=false; assert(trigger->GetTarget()==&low && "invalid attacker selected"); *flag=true;
    }
    high.instance=2;
    assert(trigger->GetTarget()==&low && "other instance selected"); high.instance=1;
    high.phase=2;
    assert(trigger->GetTarget()==&low && "other phase selected"); high.phase=1;
    high.distance=41;
    assert(trigger->GetTarget()==&low && "out-of-range attacker selected"); high.distance=10;
    ai.context.targets["current target"].value=&high;
    ai.context.attackers.value={2,3};
    assert(trigger->GetTarget()==&low && "current target change ignored");
    ai.context.targets["current target"].value=&current;
    ai.context.attackers.value={2,3};
    assert(action->isUseful() && action->isPossible());
    high.scatter=true; // Control landed after the readiness checks.
    assert(action->Execute(Event{}) && ai.castTarget==&low && "execution must reselect after control");
    low.scatter=true;
    assert(!trigger->IsActive() && !action->isUseful());
    uint32 casts=ai.casts;
    assert(!action->Execute(Event{}) && ai.casts==casts && "all controlled must not cast");
    low.scatter=false; low.health=79;
    assert(!trigger->IsActive() && !action->isUseful() && "attacker lifetime gate lost");
    assert(!action->Execute(Event{}) && ai.casts==casts && "execution must retain lifetime gate");
    low.health=80;
    assert(trigger->IsActive() && action->isUseful());
    ai.castAllowed=false;
    assert(!action->isPossible() && !action->Execute(Event{}) && "native cast rejection lost");
    std::vector<TriggerNode*> nodes;
    DpsAoeHunterStrategy{}.InitTriggers(nodes);
    checkHandler(nodes,"serpent sting on attacker","serpent sting on attacker",17,trigger,actions,ai);
    for (auto node:nodes) delete node;
    ai.context.attackers.value.clear();
    assert(!trigger->GetTarget() && !action->GetTarget());
}
int main() {
    checkStingAttacker();
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
            ('attacker-registration', 'creators["serpent sting on attacker"] = &HunterTriggerFactoryInternal', 'creators["missing attacker sting"] = &HunterTriggerFactoryInternal', 'attacker Serpent Sting unreachable'),
            ('attacker-cc', 'unit->HasBreakableByDamageCrowdControlAura()', 'false', 'breakable CC must not attract Serpent Sting'),
            ('attacker-root', 'unit->HasBreakableByDamageAuraType(SPELL_AURA_MOD_ROOT)', 'false', 'breakable CC must not attract Serpent Sting'),
            ('attacker-current', 'unit == current ||', 'false ||', 'must select healthiest secondary attacker'),
            ('attacker-owner', 'botAI->HasAura("serpent sting", unit, false, true)', 'botAI->HasAura("serpent sting", unit, false, false)', 'foreign attacker aura must not block ours'),
            ('attacker-execute', 'Unit* target = GetTarget();\n    return target && botAI->CastSpell(spell, target);', 'return botAI->CastSpell(spell, botAI->units[2]);', 'execution must reselect after control'),
            ('attacker-execute-useful', 'if (!CastDebuffSpellOnAttackerAction::isUseful())', 'if (false)', 'execution must retain lifetime gate'),
        ]
        for name, before, after, assertion in mutations:
            assert cpp.count(before) == 1, name
            result = run(cpp.replace(before, after, 1))
            assert result.returncode and assertion in result.stderr, (name, result.stderr)
            print('Detected mutation:', name)
