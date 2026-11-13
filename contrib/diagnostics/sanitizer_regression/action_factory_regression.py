#!/usr/bin/env python3
"""Instantiate production factories and repaired spell classes with bounded doubles.

The real NamedObjectFactory/Context and registrations are compiled. Unrelated
actions and spell/world services are doubles; native spell validation/effects
remain the responsibility of playerbot_cast_regression and live checks.
"""
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
base = root / "modules/mod_playerbots/src/strategy"


def block(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def clazz(text, name):
    return block(text, "class " + name + " :") + ";\n"


files = {
    "MageAiObjectContextInternal": "Classes/mage/MageAiObjectContext.cpp",
    "WarriorAiObjectContextInternal": "Classes/warrior/WarriorAIObjectContext.cpp",
    "WarlockAiObjectContextInternal": "Classes/warlock/WarlockAiObjectContext.cpp",
    "PaladinAiObjectContextInternal": "Classes/paladin/PaladinAiObjectContext.cpp",
    "ActionContext": "actions/ActionContext.h",
}
factories = "\n".join(clazz((base / path).read_text(), name) for name, path in files.items())
implemented = []
real_names = set()
for path, names in {
    "Classes/mage/MageActions.h": ["CastCombustionAction", "CastInvisibilityAction", "CastFrostBombAction", "CastLivingBombOnAttackersAction"],
    "Classes/warlock/WarlockActions.h": ["CastHowlOfTerrorAction"],
    "Classes/paladin/PaladinActions.h": ["CastWordOfGloryAction", "CastWordOfGloryOnPartyAction"],
}.items():
    source = (base / path).read_text()
    for name in names:
        implemented.append(clazz(source, name))
        real_names.add(name)

# Keep the production macro invocation too: changing BUFF_ACTION to SPELL_ACTION
# must change the target observed by this test.
for path, names in {
    "Classes/warlock/WarlockActions.h": ["CastDarkBarginAction"],
    "Classes/warrior/WarriorActions.h": ["CastPummelAction", "CastDragonroarAction"],
    "Classes/paladin/PaladinActions.h": ["CastSealOfTruthAction", "CastSealOfInsightAction", "CastSealOfCommandAction", "CastSealOfRighteousnessAction", "CastJudgementAction"],
}.items():
    source = (base / path).read_text()
    for name in names:
        implemented.append(re.search(r'\w+_ACTION\(' + name + r', [^\n]+', source).group())
        real_names.add(name)

dummy_names = set(re.findall(r'new (\w+)\(botAI\)', factories)) - real_names
dummy_names |= set(re.findall(r'new (\w+)\(ai\)', factories)) - real_names
dummy_names.discard("CastDebuffSpellOnAttackerAction")
dummies = "\n".join(f'class {name} : public Action {{ public: {name}(PlayerbotAI* ai) : Action(ai, "unexamined:{name}") {{}} }};'
                    for name in sorted(dummy_names))

named = (base / "NamedObjectContext.h").read_text()
named = "\n".join(line for line in named.splitlines() if not line.startswith('#include "'))
prefix = r'''
#include <cassert>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <cwctype>
#include <sstream>
#include <string>
#include <map>
#include <vector>
#include <list>
#include <set>
#include <unordered_map>
#include <unordered_set>
using int32 = int32_t;
using uint32 = uint32_t;
struct Player;
struct PlayerbotAI {
    std::set<std::string> auras;
    bool HasAura(std::string const& name, Player*) { return auras.contains(name); }
};
struct SealTrigger {
    PlayerbotAI* botAI;
    Player* bot = nullptr;
    bool IsActive();
};
// Database/world objects below are doubles. The name resolver itself is real.
// Spell 20271's enUS name was checked against local DBC; see the source audit.
enum { PLAYERSPELL_REMOVED = 1, PETSPELL_REMOVED = 1, SPELL_EFFECT_LEARN_SPELL = 36 };
enum LocaleConstant { LOCALE_enUS };
struct PlayerSpell { int state = 0; bool active = true; };
using PlayerSpellMap = std::map<uint32, PlayerSpell*>;
struct PetSpell { int state = 0; };
using PetSpellMap = std::map<uint32, PetSpell>;
struct Pet { PetSpellMap m_spells; };
struct Player {
    PlayerSpellMap spells;
    PlayerSpellMap& GetSpellMap() { return spells; }
    Pet* GetPet() { return nullptr; }
};
struct SpellInfo {
    char const* SpellName;
    char const* Rank = "";
    bool passive = false;
    struct Effect { int Effect = 0; } Effects[1];
    bool IsPassive() const { return passive; }
};
struct SpellStore {
    SpellInfo judgment{"Judgment"};
    SpellInfo const* GetSpellInfo(uint32 id) { return id == 20271 ? &judgment : nullptr; }
} store;
SpellStore* sSpellMgr = &store;
struct PlayerbotChatHandler {
    explicit PlayerbotChatHandler(Player*) {}
    uint32 extractSpellId(std::string const&) { return 0; }
};
bool Utf8toWStr(std::string const& in, std::wstring& out) { out.assign(in.begin(), in.end()); return true; }
void wstrToLower(std::wstring& text) { std::transform(text.begin(), text.end(), text.begin(), towlower); }
bool Utf8FitTo(char const* text, std::wstring const& expected) {
    std::wstring converted;
    Utf8toWStr(text, converted);
    wstrToLower(converted);
    return converted.find(expected) != std::wstring::npos;
}
#define TC_LOG_ERROR(...) ((void)0)
struct SpellIdValue {
    Player* bot;
    std::string qualifier;
    uint32 Calculate();
};
enum class ActionThreatType { Single, Aoe };
class NextAction;
class Action {
public:
    std::string spell;
    Action(PlayerbotAI*, std::string name) : spell(name) {}
    virtual ~Action() = default;
    virtual std::string const GetTargetName() { return "current target"; }
    virtual std::string const getName() { return spell; }
    virtual ActionThreatType getThreatType() { return ActionThreatType::Single; }
    virtual NextAction** getPrerequisites() { return nullptr; }
    virtual NextAction** getAlternatives() { return nullptr; }
    virtual NextAction** getContinuers() { return nullptr; }
    void Update() {}
    void Reset() {}
    std::string Format() { return spell; }
};
struct CastSpellAction : Action { using Action::Action; };
struct CastMeleeSpellAction : CastSpellAction { using CastSpellAction::CastSpellAction; };
struct CastDebuffSpellAction : CastSpellAction {
    CastDebuffSpellAction(PlayerbotAI* ai, std::string spell, bool = false) : CastSpellAction(ai, spell) {}
};
struct CastDebuffSpellOnAttackerAction : CastDebuffSpellAction {
    CastDebuffSpellOnAttackerAction(PlayerbotAI* ai, std::string spell, bool = true) : CastDebuffSpellAction(ai, spell) {}
    std::string const GetTargetName() override { return "attacker without aura"; }
};
struct CastBuffSpellAction : CastSpellAction {
    using CastSpellAction::CastSpellAction;
    std::string const GetTargetName() override { return "self target"; }
};
struct CastHealingSpellAction : CastBuffSpellAction { using CastBuffSpellAction::CastBuffSpellAction; };
struct HealPartyMemberAction : CastHealingSpellAction {
    using CastHealingSpellAction::CastHealingSpellAction;
    std::string const GetTargetName() override { return "party member to heal"; }
};
'''
macros = (base / "AiObject.h").read_text().splitlines()
for name in ("BUFF_ACTION", "SPELL_ACTION", "MELEE_ACTION", "ACTION_NODE", "ACTION_NODE_A"):
    start = next(i for i, line in enumerate(macros) if line.startswith("#define " + name + "("))
    end = start
    while macros[end].endswith("\\"):
        end += 1
    prefix += "\n".join(macros[start:end + 1]) + "\n"

# Compile the actual strategy handler and both factories. A factory-only test
# previously missed the strategy still asking for "forst bomb" in the r3 run.
action_h = (base / "Action.h").read_text()
action_cpp = (base / "Action.cpp").read_text()
chain = block(action_h, "class NextAction\n") + ";\n"
for signature in ("uint32 NextAction::size", "NextAction** NextAction::clone",
                  "NextAction** NextAction::merge", "NextAction** NextAction::array",
                  "void NextAction::destroy"):
    chain += block(action_cpp, signature) + "\n"
chain += r'''
struct Trigger : Action {
    using Action::Action;
    NextAction** getHandlers() { return nullptr; }
};
struct DebuffTrigger : Trigger {
    DebuffTrigger(PlayerbotAI* ai, std::string name, int, bool) : Trigger(ai, name) {}
};
'''
chain += clazz((base / "Classes/mage/MageTriggers.h").read_text(), "FrostBombTrigger")
trigger_factory = clazz((base / "Classes/mage/MageAiObjectContext.cpp").read_text(), "MageTriggerFactoryInternal")
for name in sorted(set(re.findall(r'new (\w+)\(botAI\)', trigger_factory)) - {"FrostBombTrigger"}):
    chain += f'class {name} : public Trigger {{ public: {name}(PlayerbotAI* ai) : Trigger(ai, "unexamined:{name}") {{}} }};\n'
chain += trigger_factory
chain += block((base / "Trigger.h").read_text(), "class TriggerNode\n") + ";\n"
chain += r'''
constexpr float ACTION_HIGH = 20, ACTION_NORMAL = 10, ACTION_DEFAULT = 5, ACTION_CRITICAL_HEAL = 70;
struct GenericMageStrategy { void InitTriggers(std::vector<TriggerNode*>&) {} };
struct FrostMageStrategy : GenericMageStrategy { void InitTriggers(std::vector<TriggerNode*>& triggers); };
'''
chain += block((base / "Classes/mage/FrostMageStrategy.cpp").read_text(),
               "void FrostMageStrategy::InitTriggers") + "\n"
chain += block(action_h, "class ActionNode\n") + ";\n"
chain += clazz((base / "Strategy.cpp").read_text(), "ActionNodeFactoryInternal")
chain += clazz((base / "Classes/mage/GenericMageStrategy.cpp").read_text(), "GenericMageStrategyActionNodeFactory")
chain += clazz((base / "Classes/paladin/GenericPaladinStrategyActionNodeFactory.h").read_text(),
               "GenericPaladinStrategyActionNodeFactory")
chain += r'''
// The production parent factory matters: Tank's factory must take precedence.
// Unrelated parent triggers and spell execution are outside this fixture.
struct GenericPaladinStrategy {
    PlayerbotAI* botAI;
    NamedObjectFactoryList<ActionNode> actionNodeFactories;
    explicit GenericPaladinStrategy(PlayerbotAI* ai) : botAI(ai) {
        actionNodeFactories.Add(new GenericPaladinStrategyActionNodeFactory());
    }
    void InitTriggers(std::vector<TriggerNode*>&) {}
};
struct TankPaladinStrategy : GenericPaladinStrategy {
    explicit TankPaladinStrategy(PlayerbotAI* ai);
    void InitTriggers(std::vector<TriggerNode*>&);
};
'''
tank_source = (base / "Classes/paladin/TankPaladinStrategy.cpp").read_text()
chain += clazz(tank_source, "TankPaladinStrategyActionNodeFactory")
chain += block(tank_source, "TankPaladinStrategy::TankPaladinStrategy") + "\n"
chain += block(tank_source, "void TankPaladinStrategy::InitTriggers") + "\n"

checks = r'''
void Qualified::Qualify(int value) { qualifier = std::to_string(value); }
void check(NamedObjectContext<Action>& factory, PlayerbotAI& ai, char const* key,
           char const* spell, char const* target) {
    Action* action = factory.create(key, &ai);
    assert(action && action->spell == spell && action->GetTargetName() == target);
    assert(factory.create(key, &ai) == action);
}
int main() {
    PlayerbotAI ai;
    MageAiObjectContextInternal mage;
    MageTriggerFactoryInternal mageTriggers;
    FrostMageStrategy frost;
    std::vector<TriggerNode*> nodes;
    frost.InitTriggers(nodes);
    unsigned bombHandlers = 0;
    for (TriggerNode* node : nodes) {
        if (node->getName() == "frost bomb") {
            auto trigger = dynamic_cast<FrostBombTrigger*>(mageTriggers.create(node->getName(), &ai));
            assert(trigger && trigger->spell == "frost bomb");
            node->setTrigger(trigger);
            NextAction** handlers = node->getHandlers();
            assert(NextAction::size(handlers) == 1);
            auto action = dynamic_cast<CastFrostBombAction*>(mage.create(handlers[0]->getName(), &ai));
            assert(action && action->spell == "frost bomb" && action->GetTargetName() == "current target");
            assert(handlers[0]->getRelevance() == 19.0f);
            ++bombHandlers;
            NextAction::destroy(handlers);
        }
        delete node;
    }
    assert(bombHandlers == 1);
    check(mage, ai, "combustion", "combustion", "current target");
    check(mage, ai, "invisibility", "invisibility", "self target");
    check(mage, ai, "frost bomb", "frost bomb", "current target");
    check(mage, ai, "living bomb on attackers", "living bomb", "attacker without aura");
    check(mage, ai, "frost bomb on attackers", "frost bomb", "attacker without aura");
    check(mage, ai, "nether tempest on attackers", "nether tempest", "attacker without aura");
    assert(!mage.create("forst bomb", &ai));
    WarriorAiObjectContextInternal warrior;
    check(warrior, ai, "pummel", "pummel", "current target");
    check(warrior, ai, "dragon roar", "dragon roar", "current target");
    WarlockAiObjectContextInternal warlock;
    check(warlock, ai, "dark bargain", "dark bargain", "self target");
    check(warlock, ai, "howl of terror", "howl of terror", "current target");
    PaladinAiObjectContextInternal paladin;
    // enUS Spell.dbc 20271 is Judgment; keep the old factory key as an alias.
    check(paladin, ai, "judgment", "judgment", "current target");
    check(paladin, ai, "judgement", "judgment", "current target");
    Player player;
    PlayerSpell known;
    player.spells[20271] = &known;
    SpellIdValue lookup{&player, paladin.create("judgment", &ai)->spell};
    assert(lookup.Calculate() == 20271);
    lookup.qualifier = "judgement";
    assert(lookup.Calculate() == 0);
    lookup.qualifier = paladin.create("judgement", &ai)->spell;
    assert(lookup.Calculate() == 20271);
    known.active = false;
    assert(lookup.Calculate() == 0);
    known.active = true;
    known.state = PLAYERSPELL_REMOVED;
    assert(lookup.Calculate() == 0);
    known.state = 0;
    store.judgment.passive = true;
    assert(lookup.Calculate() == 0);
    store.judgment.passive = false;
    player.spells.clear();
    assert(lookup.Calculate() == 0);
    SealTrigger seal{&ai};
    assert(seal.IsActive());
    for (auto const* name : {"seal of command", "seal of truth", "seal of righteousness",
                             "seal of justice", "seal of insight"}) {
        ai.auras = {name};
        assert(!seal.IsActive());
    }
    ai.auras.clear();
    check(paladin, ai, "word of glory", "word of glory", "self target");
    check(paladin, ai, "word of glory on party", "word of glory", "party member to heal");
    check(paladin, ai, "seal of insight", "seal of insight", "self target");
    check(paladin, ai, "seal of truth", "seal of truth", "self target");
    TankPaladinStrategy tank(&ai);
    nodes.clear();
    tank.InitTriggers(nodes);
    unsigned sealHandlers = 0;
    for (TriggerNode* node : nodes) {
        Trigger trigger(&ai, node->getName());
        node->setTrigger(&trigger);
        NextAction** handlers = node->getHandlers();
        for (unsigned i = 0; i < NextAction::size(handlers); ++i) {
            auto name = handlers[i]->getName();
            assert(name != "seal of wisdom" && name != "seal of corruption" && name != "seal of vengeance");
            // Low mana must not replace the current seal with a fake mana source.
            assert(node->getName() != "low mana" || !name.starts_with("seal of "));
        }
        if (node->getName() == "seal") {
            ++sealHandlers;
            assert(NextAction::size(handlers) == 1);
            assert(handlers[0]->getName() == "seal of insight");
            assert(handlers[0]->getRelevance() == ACTION_HIGH);
        }
        NextAction::destroy(handlers);
        delete node;
    }
    assert(sealHandlers == 1);
    // Follow the real fallback graph, including the generic terminal node.
    std::vector<std::string> seals{"seal of insight", "seal of truth", "seal of command", "seal of righteousness"};
    for (unsigned i = 0; i < seals.size(); ++i) {
        ActionNode* node = tank.actionNodeFactories.GetContextObject(seals[i], &ai);
        assert(node && node->getName() == seals[i]);
        check(paladin, ai, seals[i].c_str(), seals[i].c_str(), "self target");
        node->setAction(paladin.create(seals[i], &ai));
        NextAction** alternatives = node->getAlternatives();
        if (i + 1 < seals.size()) {
            assert(NextAction::size(alternatives) == 1);
            assert(alternatives[0]->getName() == seals[i + 1]);
        } else assert(NextAction::size(alternatives) == 0);
        NextAction::destroy(alternatives);
        delete node;
    }
    ActionContext general;
    assert(dynamic_cast<CombatFormationMoveAction*>(general.create("combat formation move", &ai)));
    assert(dynamic_cast<CastShootAction*>(general.create("shoot", &ai)));
    assert(dynamic_cast<ApplyOilAction*>(general.create("apply oil", &ai)));
    GenericMageStrategyActionNodeFactory mageNodes;
    ActionNode* evocation = mageNodes.create("evocation", &ai);
    assert(evocation);
    evocation->setAction(mage.create("evocation", &ai));
    NextAction** manaFallback = evocation->getAlternatives();
    assert(NextAction::size(manaFallback) == 1 && manaFallback[0]->getName() == "mana potion");
    assert(dynamic_cast<ManaPotionAction*>(general.create(manaFallback[0]->getName(), &ai)));
    NextAction::destroy(manaFallback);
    delete evocation;
    ActionNodeFactoryInternal defaultNodes;
    ActionNode* random = defaultNodes.create("move random", &ai);
    assert(random);
    random->setAction(general.create("move random", &ai));
    NextAction** fallback = random->getAlternatives();
    assert(NextAction::size(fallback) == 1 && fallback[0]->getName() == "stay line");
    assert(dynamic_cast<StayLineAction*>(general.create(fallback[0]->getName(), &ai)));
    NextAction::destroy(fallback);
    delete random;
}
'''

for path, forbidden, required in (
    ("Classes/warlock/GenericWarlockStrategy.cpp", '"dark bargaing"', '"dark bargain"'),
    ("Classes/warrior/GenericWarriorStrategy.cpp", '"dragon_roar"', '"dragon roar"'),
    ("Classes/paladin/TankPaladinStrategy.cpp", '"judgement of wisdom"', '"judgment"'),
):
    source = (base / path).read_text()
    assert forbidden not in source and required in source, path

with tempfile.TemporaryDirectory(prefix="loa-action-factories-") as directory:
    cpp = Path(directory) / "test.cpp"
    exe = Path(directory) / "test"
    resolver = block((base / "value/SpellIdValue.cpp").read_text(), "uint32 SpellIdValue::Calculate()")
    seal = block((base / "Classes/paladin/PaladinTriggers.cpp").read_text(), "bool SealTrigger::IsActive()")
    cpp.write_text("\n".join((prefix, named, dummies, *implemented, factories, chain, resolver, seal, checks)))
    subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
    if "--verify-mutations" in sys.argv:
        original = cpp.read_text()
        mutations = {
            "action registration": ('creators["frost bomb"] = &MageAiObjectContextInternal::frost_bomb;',
                                    'creators["forst bomb"] = &MageAiObjectContextInternal::frost_bomb;'),
            "trigger registration": ('creators["frost bomb"] = &MageTriggerFactoryInternal::frost_bomb;',
                                     'creators["forst bomb"] = &MageTriggerFactoryInternal::frost_bomb;'),
            "strategy trigger": ('new TriggerNode("frost bomb",', 'new TriggerNode("forst bomb",'),
            "strategy action": ('new NextAction("frost bomb", 19.0f)', 'new NextAction("forst bomb", 19.0f)'),
            "tank seal handler": ('new NextAction("seal of insight", ACTION_HIGH)',
                                  'new NextAction("seal of corruption", ACTION_HIGH)'),
            "tank low-level fallback": ('ACTION_NODE_A(seal_of_truth, "seal of truth", "seal of command")',
                                        'ACTION_NODE_A(seal_of_truth, "seal of truth", "seal of corruption")'),
        }
        for label, (before, after) in mutations.items():
            assert original.count(before) == 1, label
            cpp.write_text(original.replace(before, after))
            subprocess.run([compiler, "-std=c++20", "-O0", str(cpp), "-o", str(exe)], check=True)
            result = subprocess.run([str(exe)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
            assert result.returncode != 0, "Undetected mutation: " + label
            print("Detected mutation:", label)
print("Repaired Action factories and spell target contracts passed")
