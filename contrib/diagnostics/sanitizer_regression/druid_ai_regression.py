#!/usr/bin/env python3
"""Compile real Druid factories/predicates/actions against bounded world doubles.

Player state, aura lookup and core cast validation are doubles. This checks the
strategy-to-trigger contracts and state transitions, not a live rotation or DPS.
The separate native BG run supplies real spell/form coverage. Mutation checks
prove that missing registration, stale combo ownership, enemy-target buffs and
wrong Eclipse direction are detected.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]
base = root / 'modules/mod_playerbots/src/strategy'
druid = base / 'Classes/druid'


def block(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def clazz(source, name):
    return block(source, 'class ' + name + ' :') + ';\n'


def strip_includes(source):
    return '\n'.join(line for line in source.splitlines() if not line.startswith('#include "')) + '\n'


prefix = r'''
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <iostream>
#include <functional>
#define TC_LOG_DEBUG(...) ((void)0)
struct ActionExecutionTrace { static bool Enabled() { return false; } };
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using int32 = std::int32_t;
constexpr uint32 IN_MILLISECONDS = 1000;
enum ShapeshiftForm { FORM_NONE, FORM_CAT, FORM_BEAR, FORM_MOONKIN };
constexpr int POWER_ENERGY = 3, SPEC_DRUID_BALANCE = 102, SPEC_DRUID_RESTORATION = 105;
constexpr uint32 DISPEL_MAGIC = 1, DISPEL_CURSE = 2, DISPEL_POISON = 4;
constexpr int SPELL_FAILED_NOT_SHAPESHIFT = 1;
struct SpellInfo { int shapeResult = 0; int CheckShapeshift(int) const { return shapeResult; } };
struct SpellMgr { SpellInfo info; SpellInfo const* GetSpellInfo(uint32 id) { return id ? &info : nullptr; } };
SpellMgr manager; SpellMgr* sSpellMgr = &manager;
struct WorldPacket {};
struct Event {
    bool active = false;
    Event() = default;
    explicit Event(std::string const&) : active(true) {}
    explicit operator bool() const { return active; }
};
uint32 getMSTime() { return 1000; }
struct Aura { int32 duration; bool owner = true; int32 GetDuration() const { return duration; } };
struct Unit {
    bool alive = true, world = true, petGuardian = false, friendly = true;
    std::set<uint32> harmful;
    bool IsPetGuardianStuff() const { return petGuardian; }
    float health = 100;
    std::set<uint32> auras;
    bool IsAlive() const { return alive; }
    bool IsInWorld() const { return world; }
    float GetHealthPct() const { return health; }
    float GetHealth() const { return health; }
    bool HasAura(uint32 id) const { return auras.count(id); }
};
struct Player : Unit {
    Unit* comboTarget = nullptr;
    Unit* pet = nullptr;
    Unit* GetPet() { return pet; }
    uint8 points = 0;
    int energy = 100, spec = SPEC_DRUID_BALANCE;
    ShapeshiftForm form = FORM_NONE;
    bool mounted = false, flying = false, taxi = false;
    std::set<uint32> known;
    Unit* GetComboTarget() const { return comboTarget; }
    uint8 GetComboPoints() const { return points; }
    bool IsFriendlyTo(Unit* target) const { return target->friendly; }
    bool HasSpell(uint32 id) const { return known.count(id); }
    bool IsMounted() const { return mounted; }
    bool IsFlying() const { return flying; }
    bool IsInFlight() const { return taxi; }
    bool IsWithinMeleeRange(Unit*) const { return true; }
    ShapeshiftForm GetShapeshiftForm() const { return form; }
    int GetPower(int) const { return energy; }
    int GetTalentSpecialization() const { return spec; }
};
using Pet = Unit;
struct UntypedValue { virtual ~UntypedValue() = default; virtual void Update() {} virtual void Reset() {} };
template<class T> struct Value : UntypedValue {
    T value{}; Value() = default; Value(T value) : value(value) {}
    virtual T Get() { return value; }
};
struct Context {
    std::map<std::string, Value<Unit*>> targets;
    Value<float> dps{1};
    Value<bool> useful{true};
    template<class T> Value<T>* GetValue(std::string const& name, uint32 qualifier) {
        return GetValue<T>(name + ":" + std::to_string(qualifier));
    }
    std::function<Unit*()> markTarget;
    template<class T> Value<T>* GetValue(std::string const& name, std::string const& = "") {
        if constexpr (std::is_same_v<T, float>) return &dps;
        else if constexpr (std::is_same_v<T, bool>) return &useful;
        else {
            if (name == "mark of the wild target" && markTarget) targets[name].value = markTarget();
            return &targets[name];
        }
    }
};
struct PlayerbotAI {
    Player* player;
    Context context;
    std::vector<Player*> group;
    bool canCast = true;
    Unit* checkedTarget = nullptr;
    std::string checkedSpell;
    std::map<std::pair<std::string, Unit*>, Aura*> auras;
    Player* GetBot() { return player; }
    bool HasAuraToDispel(Unit* target, uint32 type) { return target->harmful.count(type); }
    int casts = 0;
    Context* GetAiObjectContext() { return &context; }
    bool CanCastSpell(std::string const& spell, Unit* target) {
        checkedSpell = spell; checkedTarget = target; return canCast;
    }
    Aura* GetAura(std::string const& spell, Unit* target, bool owner = false, bool = false) {
        auto aura = auras[{spell, target}];
        return aura && (!owner || aura->owner) ? aura : nullptr;
    }
    bool HasAnyAuraOf(Unit* target, ...) {
        va_list args; va_start(args, target);
        bool found = false;
        while (auto name = va_arg(args, char const*)) found |= GetAura(name, target) != nullptr;
        va_end(args); return found;
    }
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
prefix += '\n'.join(strip_includes((base / name).read_text()) for name in
                    ('Action.h', 'Action.cpp', 'Trigger.h', 'Trigger.cpp', 'NamedObjectContext.h'))
prefix += block((base / 'NamedObjectContext.cpp').read_text(), 'void Qualified::Qualify(int qual)')
generic_h = (base / 'triggers/GenericTriggers.h').read_text()
generic_cpp = (base / 'triggers/GenericTriggers.cpp').read_text()
prefix += '\n'.join(clazz(generic_h, name) for name in ('SpellTrigger', 'BuffTrigger', 'DebuffTrigger'))
prefix += '\n'.join(block(generic_cpp, sig) for sig in (
    'bool SpellTrigger::IsActive()', 'bool BuffTrigger::IsActive()', 'bool DebuffTrigger::IsActive()'))
prefix += strip_includes((base / 'triggers/CureTriggers.h').read_text())
prefix += strip_includes((base / 'triggers/CureTriggers.cpp').read_text())
# Core spell execution is outside this bounded fixture. Keep the real inherited
# buff/debuff predicates and target selection; castability is controlled explicitly.
prefix += r'''
struct CastSpellAction : Action {
    std::string spell;
    float range = 40;
    CastSpellAction(PlayerbotAI* ai, std::string const& spell) : Action(ai, spell), spell(spell) {}
    std::string const GetTargetName() override { return "current target"; }
    bool isPossible() override { return botAI->CanCastSpell(spell, GetTarget()); }
    bool Execute(Event) override { ++botAI->casts; botAI->checkedSpell = spell; return botAI->canCast; }
    NextAction** getPrerequisites() override { return nullptr; }
    bool isUseful() override { return context->useful.Get(); }
};
'''
actions_h = (base / 'actions/GenericSpellActions.h').read_text()
actions_cpp = (base / 'actions/GenericSpellActions.cpp').read_text()
prefix += '\n'.join(clazz(actions_h, name) for name in (
    'CastAuraSpellAction', 'CastBuffSpellAction', 'CastDebuffSpellAction', 'CastMeleeSpellAction'))
prefix += '\n'.join(block(actions_cpp, sig) for sig in (
    'bool CastAuraSpellAction::isUseful()', 'bool CastDebuffSpellAction::isUseful()',
    'bool CastMeleeSpellAction::isUseful()', 'CastBuffSpellAction::CastBuffSpellAction('))
prefix += 'CastMeleeSpellAction::CastMeleeSpellAction(PlayerbotAI* ai, std::string const spell) : CastSpellAction(ai, spell) {}\n'

# Use the real party-member traversal for player/pet ordering. Spatial checks
# and the outer group/role list are bounded; the Druid predicate is production.
party_source = (base / 'value/PartyMemberValue.cpp').read_text()
prefix += block((base / 'value/PartyMemberValue.h').read_text(), 'class FindPlayerPredicate') + ';\n'
prefix += r'''
struct PartyMemberValue : Value<Unit*>, AiNamedObject {
    PartyMemberValue(PlayerbotAI* ai, std::string const& name) : AiNamedObject(ai, name) {}
    virtual Unit* Calculate() = 0;
    Unit* Get() override { return Calculate(); }
    bool Check(Unit* unit) { return unit->IsInWorld(); }
    Unit* FindPartyMember(std::vector<Player*>* party, FindPlayerPredicate& predicate);
    Unit* FindPartyMember(FindPlayerPredicate& predicate) { return FindPartyMember(&botAI->group, predicate); }
};
'''
prefix += block(party_source, 'Unit* PartyMemberValue::FindPartyMember(std::vector<Player*>*')
values = strip_includes((druid / 'DruidValues.h').read_text())
values += strip_includes((druid / 'DruidValues.cpp').read_text())

triggers = strip_includes((druid / 'DruidTriggers.h').read_text())
triggers += strip_includes((druid / 'DruidTriggers.cpp').read_text())
context_source = (druid / 'DruidAiObjectContext.cpp').read_text()
assert 'triggerContexts.Add(new DruidTriggerFactoryInternal());' in context_source
factory = clazz(context_source, 'DruidTriggerFactoryInternal')
factory += clazz(context_source, 'DruidValueFactoryInternal')
assert 'valueContexts.Add(new DruidValueFactoryInternal());' in context_source
actions = '\n'.join(clazz((druid / file).read_text(), name) for file, name in (
    ('DruidCatActions.h', 'CastSavageRoarAction'), ('DruidCatActions.h', 'CastTigersFuryAction'),
    ('DruidCatActions.h', 'CastMangleCatAction'), ('DruidCatActions.h', 'CastSwipeCatAction'),
    ('DruidBearActions.h', 'CastMangleBearAction'), ('DruidBearActions.h', 'CastSwipeBearAction'),
    ('DruidActions.h', 'CastFaerieFireFeralAction')))
actions += strip_includes((druid / 'DruidCatActions.cpp').read_text())
actions += block(actions_h, 'class PartyMemberActionNameSupport') + ';\n'
actions += clazz(actions_h, 'BuffOnPartyAction')
actions += block(actions_cpp, 'Value<Unit*>* BuffOnPartyAction::GetTargetValue()')
actions += clazz((druid / 'DruidActions.h').read_text(), 'CastMarkOfTheWildOnPartyAction')
actions += block((druid / 'DruidActions.cpp').read_text(), 'Value<Unit*>* CastMarkOfTheWildOnPartyAction::GetTargetValue()')
actions += block((druid / 'DruidActions.cpp').read_text(), 'bool CastMarkOfTheWildOnPartyAction::Execute(')

actions += clazz(actions_h, 'CurePartyMemberAction')
actions += block(actions_cpp, 'Value<Unit*>* CurePartyMemberAction::GetTargetValue()')
for name in ('DruidDispelAction', 'CastCurePoisonAction', 'CastCurePoisonOnPartyAction',
             'CastAbolishPoisonAction', 'CastAbolishPoisonOnPartyAction', 'CastDruidRemoveCurseOnPartyAction'):
    actions += clazz((druid / 'DruidActions.h').read_text(), name)
for sig in ('bool DruidDispelAction::SelectSpell()', 'Value<Unit*>* DruidDispelAction::GetTargetValue()',
            'bool DruidDispelAction::isUseful()', 'bool DruidDispelAction::isPossible()',
            'NextAction** DruidDispelAction::getPrerequisites()', 'bool DruidDispelAction::Execute('):
    actions += block((druid / 'DruidActions.cpp').read_text(), sig)
# Extract the actual cure registrations/creators, keeping unrelated Actions outside this fixture.
action_factory = clazz(context_source, 'DruidAiObjectContextInternal')
cure_creators = ('cure_poison', 'cure_poison_on_party', 'abolish_poison',
                 'abolish_poison_on_party', 'remove_curse_on_party', 'cure_magic_on_party')
actions += 'class DruidCureActions : public NamedObjectContext<Action> { public: DruidCureActions() {\n'
for method in cure_creators:
    registration = re.search(r'^.*creators\[.*= &DruidAiObjectContextInternal::' + method + r';$', action_factory, re.M)
    assert registration, method
    actions += registration.group().replace('DruidAiObjectContextInternal::', 'DruidCureActions::') + '\n'
actions += '}\n'
for method in cure_creators:
    actions += block(action_factory, 'static Action* ' + method + '(')
actions += '};\n'

# Compile actual local handlers, with only their generic parent outside this test.
strategies = '\n'.join(re.findall(r'^static float ACTION_.*;$', (base / 'Strategy.h').read_text(), re.M))
strategies += r'''
struct DruidCureStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct NonCombatStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct GenericDruidNonCombatStrategy : NonCombatStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct FeralDruidStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct GenericDruidStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct CatDpsDruidStrategy : FeralDruidStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct BearTankDruidStrategy : FeralDruidStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
struct CasterDruidStrategy : GenericDruidStrategy { void InitTriggers(std::vector<TriggerNode*>&); };
'''
for name in ('CatDpsDruidStrategy', 'BearTankDruidStrategy', 'CasterDruidStrategy'):
    strategies += block((druid / (name + '.cpp')).read_text(), 'void ' + name + '::InitTriggers(')

strategies += block((druid / 'GenericDruidStrategy.cpp').read_text(), 'void DruidCureStrategy::InitTriggers(')
strategies += block((druid / 'GenericDruidNonCombatStrategy.cpp').read_text(), 'void GenericDruidNonCombatStrategy::InitTriggers(')

tests = r'''
int main() {
    Player bot; Unit target, other;
    PlayerbotAI ai{&bot};
    ai.context.targets["self target"].value = &bot;
    ai.context.targets["current target"].value = &target;
    ai.context.targets["mark of the wild target"].value = &other;
    DruidTriggerFactoryInternal factory;
    auto active = [&](std::string const& name) {
        auto trigger = factory.create(name, &ai);
        assert(trigger && "required Druid trigger missing");
        return trigger->IsActive();
    };
    for (auto name : {"cat form", "bear form", "combo points not full",
        "combo points not full and high energy", "combo points available", "ferocious bite time",
        "target with combo points almost dead", "savage roar", "rake", "moonfire", "faerie fire",
        "faerie fire (feral)", "mark of the wild", "mark of the wild on party", "berserk",
        "eclipse (lunar)", "eclipse (solar)", "eclipse (lunar) cooldown", "eclipse (solar) cooldown"})
        assert(factory.create(name, &ai) && "required Druid trigger missing");

    assert(!active("cat form"));
    bot.known = {768, 5487, 52610, 1822, 8921, 770, 1126, 2912, 5176, 106951, 50334};
    assert(active("cat form") && "formless feral must request Cat Form");
    bot.mounted = true; assert(!active("cat form")); bot.mounted = false;
    bot.flying = true; assert(!active("cat form")); bot.flying = false;
    bot.alive = false; assert(!active("cat form")); bot.alive = true;
    bot.form = FORM_CAT; assert(!active("cat form"));
    assert(active("bear form")); bot.form = FORM_BEAR; assert(!active("bear form"));
    bot.form = FORM_CAT;
    bot.comboTarget = &target;
    assert(active("combo points not full"));
    bot.energy = 59; assert(!active("combo points not full and high energy"));
    bot.energy = 60; assert(active("combo points not full and high energy"));
    bot.points = 4; assert(!active("combo points available"));
    bot.points = 5;
    assert(active("combo points available") && active("ferocious bite time"));
    assert(!active("combo points not full"));
    bot.comboTarget = &other;
    assert(!active("combo points available") && "combo points belong to another target");
    bot.comboTarget = &target;
    bot.points = 0;
    assert(!active("combo points available") && "spent points must not trigger a finisher");
    bot.points = 5; target.alive = false;
    assert(!active("combo points available") && "dead target cannot enable finishers");
    target.alive = true; bot.points = 1; target.health = 14;
    assert(active("target with combo points almost dead"));
    target.health = 15; assert(!active("target with combo points almost dead"));
    target.health = 100;

    CastSavageRoarAction roar(&ai);
    assert(roar.GetTarget() == &bot && "Savage Roar must target self");
    assert(active("savage roar") && roar.isUseful());
    Aura fresh{10000}, expiring{2999}, foreign{10000, false};
    ai.auras[{"savage roar", &bot}] = &fresh;
    assert(!active("savage roar") && !roar.isUseful());
    ai.auras[{"savage roar", &bot}] = &expiring;
    assert(active("savage roar") && roar.isUseful() && "Savage Roar refresh must remain useful");
    bot.points = 0; assert(!active("savage roar")); bot.points = 1;
    bot.comboTarget = &other; assert(!active("savage roar")); bot.comboTarget = &target;

    CastTigersFuryAction fury(&ai);
    bot.form = FORM_NONE; bot.energy = 0;
    assert(!fury.isUseful() && "Tiger's Fury requires Cat Form");
    bot.form = FORM_CAT;
    assert(fury.isUseful());
    bot.auras.insert(106951);
    assert(!fury.isUseful() && "Tiger's Fury is blocked by Berserk");
    bot.auras.clear(); bot.energy = 35; assert(!fury.isUseful());
    bot.energy = 34; assert(fury.isUseful());
    ai.canCast = false; assert(!fury.isPossible()); ai.canCast = true;

    assert(active("rake"));
    ai.auras[{"rake", &target}] = &foreign;
    assert(active("rake") && "another druid's bleed must not block ours");
    ai.auras[{"rake", &target}] = &fresh; assert(!active("rake"));
    ai.auras.clear(); target.health = 5; assert(!active("rake")); target.health = 100;
    assert(active("moonfire")); bot.known.erase(8921); assert(!active("moonfire"));
    assert(active("faerie fire (feral)"));
    ai.auras[{"faerie fire", &target}] = &foreign;
    assert(!active("faerie fire (feral)")); ai.auras.clear();
    assert(active("mark of the wild") && active("mark of the wild on party"));
    ai.auras[{"blessing of kings", &bot}] = &fresh;
    assert(!active("mark of the wild"));
    ai.auras[{"legacy of the emperor", &other}] = &fresh;
    assert(!active("mark of the wild on party")); ai.auras.clear();
    assert(active("berserk") && ai.checkedTarget == &bot);
    ai.canCast = false; assert(!active("berserk")); ai.canCast = true;
    bot.form = FORM_NONE; assert(!active("berserk"));

    assert(!active("eclipse (lunar)") && !active("eclipse (solar)"));
    bot.auras = {48518, 67483};
    assert(active("eclipse (lunar)") && !active("eclipse (solar)"));
    assert(!active("eclipse (lunar) cooldown"));
    bot.auras = {67483};
    assert(active("eclipse (lunar) cooldown") && "Starfire must continue toward Solar through zero");
    assert(!active("eclipse (solar) cooldown"));
    bot.auras = {48517, 67484};
    assert(active("eclipse (solar)") && !active("eclipse (lunar)"));
    assert(!active("eclipse (solar) cooldown"));
    bot.auras = {67484};
    assert(active("eclipse (solar) cooldown") && "Wrath must continue toward Lunar through zero");
    bot.spec = 103; assert(!active("eclipse (solar) cooldown")); bot.spec = SPEC_DRUID_BALANCE;

    CastMangleCatAction catMangle(&ai); CastMangleBearAction bearMangle(&ai);
    CastSwipeCatAction catSwipe(&ai); CastSwipeBearAction bearSwipe(&ai);
    CastFaerieFireFeralAction fire(&ai);
    for (auto action : std::vector<Action*>{&catMangle, &bearMangle, &catSwipe, &bearSwipe, &fire}) {
        assert(action->isPossible());
        auto expected = action == &fire ? "faerie fire" : (action == &catMangle || action == &bearMangle) ? "mangle" : "swipe";
        assert(ai.checkedSpell == expected && "strategy alias must resolve a learned MoP spell name");
    }
    assert(catMangle.getName() == "mangle (cat)" && fire.getName() == "faerie fire (feral)");
    ai.auras[{"faerie fire", &target}] = &fresh;
    assert(!fire.isUseful() && "Faerie Fire default must respect the existing debuff");

    // A pet or already-buffed player must not starve a later eligible player.
    Player first, next; Unit pet; pet.petGuardian = true; first.pet = &pet;
    ai.group = {&first, &next};
    ai.auras[{"blessing of kings", &first}] = &fresh;
    DruidValueFactoryInternal valueFactory;
    auto markValue = dynamic_cast<Value<Unit*>*>(valueFactory.create("mark of the wild target", &ai));
    assert(markValue && "Druid Mark selector registration missing");
    assert(markValue->Get() == &next && "pet must not starve the next unbuffed player");
    ai.context.markTarget = [&] { return markValue->Get(); };
    CastMarkOfTheWildOnPartyAction partyMark(&ai);
    assert(active("mark of the wild on party"));
    assert(partyMark.GetTarget() == &next && "Mark action must use the same player selector as its trigger");
    ai.canCast = false; assert(!partyMark.Execute(Event())); ai.canCast = true;
    ai.auras[{"mark of the wild", &next}] = &fresh;
    assert(!markValue->Get() && !active("mark of the wild on party"));
    ai.auras.erase({"mark of the wild", &next}); next.alive = false;
    assert(!markValue->Get()); next.alive = true; next.world = false;
    assert(!markValue->Get()); next.world = true;
    assert(markValue->Get() == &next);

    // Learned MoP dispels, specialized capability, cached aura disappearance,
    // native rejection and real strategy/factory wiring (not invented spell effects).
    ai.context.targets["party member to dispel:4"].value = &other;
    ai.context.targets["party member to dispel:2"].value = &other;
    ai.context.targets["party member to dispel:1"].value = &other;
    DruidCureActions cureFactory;
    auto poison = cureFactory.create("cure poison on party", &ai);
    auto curse = cureFactory.create("remove curse on party", &ai);
    auto magic = cureFactory.create("nature's cure on party", &ai);
    assert(poison && curse && magic && "Druid cure Actions must be registered");
    other.harmful = {DISPEL_POISON, DISPEL_CURSE, DISPEL_MAGIC};
    bot.known.clear();
    assert(!active("party member cure poison") && !poison->isUseful() && !poison->Execute(Event()));
    bot.known = {2782, 88423}; bot.spec = SPEC_DRUID_BALANCE;
    assert(active("party member cure poison") && active("party member remove curse"));
    assert(!active("party member cure magic") && !magic->Execute(Event()) && "non-Restoration must not dispel magic");
    assert(poison->isUseful() && poison->isPossible() && ai.checkedSpell == "remove corruption");
    assert(curse->isPossible() && ai.checkedSpell == "remove corruption");
    bot.spec = SPEC_DRUID_RESTORATION;
    assert(active("party member cure magic") && magic->isPossible() && ai.checkedSpell == "nature's cure");
    assert(poison->isPossible() && ai.checkedSpell == "nature's cure" && "Restoration poison uses Nature's Cure");
    bot.known = {2782};
    assert(!active("party member cure poison") && !poison->isPossible() && "Restoration cannot fall back to an unassigned spell");
    bot.known = {88423};
    other.harmful.erase(DISPEL_POISON);
    int casts = ai.casts;
    assert(!active("party member cure poison") && !poison->isUseful() && !poison->Execute(Event()) &&
        ai.casts == casts && "cached clean target must not consume a cast");
    other.harmful.insert(DISPEL_POISON);
    other.alive = false; assert(!active("party member cure poison") && !poison->Execute(Event())); other.alive = true;
    other.world = false; assert(!active("party member cure poison") && !poison->Execute(Event())); other.world = true;
    other.friendly = false; assert(!active("party member cure poison") && !poison->Execute(Event())); other.friendly = true;
    ai.canCast = false;
    assert(!poison->Execute(Event()) && ai.casts == casts && "native refusal must remain a refusal"); ai.canCast = true;
    manager.info.shapeResult = SPELL_FAILED_NOT_SHAPESHIFT;
    for (bool taxi : {false, true}) {
        bot.flying = !taxi; bot.taxi = taxi;
        assert(!active("party member cure poison") && !poison->isUseful() && !poison->isPossible() &&
            !poison->getPrerequisites() && !poison->Execute(Event()) && ai.casts == casts &&
            "dispel must not cancel flight to satisfy shapeshift prerequisites");
    }
    bot.flying = bot.taxi = false;
    auto prerequisites = poison->getPrerequisites();
    assert(prerequisites && prerequisites[0]->getName() == "caster form"); NextAction::destroy(prerequisites);
    manager.info.shapeResult = 0; assert(!poison->getPrerequisites());
    auto legacy = cureFactory.create("abolish poison on party", &ai);
    assert(legacy && legacy->isPossible() && ai.checkedSpell == "nature's cure");
    assert(poison->Execute(Event()) && ai.casts == casts + 1);

    for (bool combat : {false, true}) {
        std::vector<TriggerNode*> cureNodes;
        if (combat) DruidCureStrategy().InitTriggers(cureNodes);
        else GenericDruidNonCombatStrategy().InitTriggers(cureNodes);
        int chains = 0;
        for (auto node : cureNodes) {
            if (node->getName() == "party member cure poison" || node->getName() == "party member remove curse" ||
                node->getName() == "party member cure magic") {
                auto resolved = factory.create(node->getName(), &ai);
                assert(resolved); node->setTrigger(resolved);
                auto handlers = node->getHandlers();
                auto action = cureFactory.create(handlers[0]->getName(), &ai);
                assert(action && action->isPossible() && ai.checkedSpell == "nature's cure");
                ++chains; NextAction::destroy(handlers);
            }
            delete node;
        }
        assert(chains == 3 && "both combat and noncombat must wire three dispel types");
    }

    std::vector<TriggerNode*> nodes;
    CatDpsDruidStrategy().InitTriggers(nodes);
    BearTankDruidStrategy().InitTriggers(nodes);
    CasterDruidStrategy().InitTriggers(nodes);
    bool catHandler = false, bearHandler = false, directionHandler = false;
    for (auto node : nodes) {
        auto trigger = factory.create(node->getName(), &ai);
        if (trigger) {
            node->setTrigger(trigger);
            auto handlers = node->getHandlers();
            if (node->getName() == "cat form") catHandler = handlers[0]->getName() == "cat form";
            if (node->getName() == "bear form") bearHandler = handlers[0]->getName() == "bear form";
            if (node->getName() == "eclipse (lunar) cooldown") directionHandler = handlers[0]->getName() == "starfire";
            NextAction::destroy(handlers);
        }
        delete node;
    }
    assert(catHandler && bearHandler && directionHandler && "restored trigger must reach the correct local handler");
    std::cout << "PASS: 22 Druid registrations, MoP dispel eligibility/aliases/strategies, live combo ownership, form/buff/debuff predicates, Eclipse and spell aliases\n";
}
'''


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


with tempfile.TemporaryDirectory(prefix='loa-druid-ai-') as directory:
    def run(label, trigger_body=triggers, factory_body=factory, action_body=actions, value_body=values, expected=None):
        binary = Path(directory) / label
        subprocess.run([compiler, '-x', 'c++', '-std=c++20', '-O1', '-g',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-', '-o', str(binary)],
                       input=prefix + value_body + trigger_body + factory_body + action_body + strategies + tests,
                       text=True, check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                env=dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',
                                         UBSAN_OPTIONS='halt_on_error=1'))
        if expected:
            assert result.returncode and 'Assertion' in result.stderr and expected in result.stderr, result.stderr
            print(f'Mutation {label}: rejected ({expected})', flush=True)
        else:
            if result.returncode:
                sys.stderr.write(result.stderr)
                raise subprocess.CalledProcessError(result.returncode, str(binary))
            print(result.stdout, end='', flush=True)

    run('current')
    if '--verify-mutations' in sys.argv[3:]:
        run('missing-cat-registration', factory_body=replace_once(factory,
            'creators["cat form"] = &DruidTriggerFactoryInternal::cat_form;', ''),
            expected='required Druid trigger missing')
        run('foreign-combo', trigger_body=replace_once(triggers,
            ' || bot->GetComboTarget() != target', ''), expected='combo points belong to another target')
        run('enemy-roar', action_body=replace_once(actions,
            ': CastBuffSpellAction(botAI, "savage roar", false, 3 * IN_MILLISECONDS) {}',
            ': CastBuffSpellAction(botAI, "savage roar", false, 3 * IN_MILLISECONDS) {}\n'
            'std::string const GetTargetName() override { return "current target"; }'),
            expected='Savage Roar must target self')
        run('no-roar-refresh', action_body=replace_once(actions, '3 * IN_MILLISECONDS', '0'),
            expected='Savage Roar refresh must remain useful')
        run('formless-fury', action_body=replace_once(actions,
            'bot->GetShapeshiftForm() == FORM_CAT && ', ''), expected="Tiger's Fury requires Cat Form")
        run('berserk-fury', action_body=replace_once(actions, '!bot->HasAura(106951) && ', ''),
            expected="Tiger's Fury is blocked by Berserk")
        run('reversed-eclipse', trigger_body=replace_once(triggers,
            'lunar ? 67483 : 67484', 'lunar ? 67484 : 67483'),
            expected='Starfire must continue toward Solar through zero')
        run('legacy-mangle', action_body=replace_once(actions,
            'CastMangleCatAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "mangle")',
            'CastMangleCatAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "mangle (cat)")'),
            expected='strategy alias must resolve a learned MoP spell name')

        run('pet-mark-loop', value_body=replace_once(values, ' && !target->IsPetGuardianStuff()', ''),
            expected='pet must not starve the next unbuffed player')
        run('missing-mark-selector', factory_body=replace_once(factory,
            'creators["mark of the wild target"] = &DruidValueFactoryInternal::mark_target;', ''),
            expected='Druid Mark selector registration missing')

        run('missing-poison-registration', factory_body=replace_once(factory,
            'creators["party member cure poison"] = &DruidTriggerFactoryInternal::cure_poison;', ''),
            expected='required Druid trigger missing')
        run('restoration-wrong-spell', action_body=replace_once(actions,
            "spell = id == 88423 ? \"nature's cure\" : \"remove corruption\";",
            'spell = "remove corruption";'), expected="ai.checkedSpell == \"nature's cure\"")
        run('cached-clean-dispel', value_body=replace_once(values,
            'ai->HasAuraToDispel(target, dispelType)', 'true'),
            expected='cached clean target must not consume a cast')
        run('ignore-native-dispel-refusal', action_body=replace_once(actions,
            'return isUseful() && isPossible() && CastSpellAction::Execute(event);',
            'return isUseful() && CastSpellAction::Execute(event);'),
            expected='native refusal must remain a refusal')

        run('cancel-flight-to-dispel', value_body=replace_once(values,
            'if (bot->IsFlying() || bot->IsInFlight())', 'if (false)'),
            expected='dispel must not cancel flight to satisfy shapeshift prerequisites')
