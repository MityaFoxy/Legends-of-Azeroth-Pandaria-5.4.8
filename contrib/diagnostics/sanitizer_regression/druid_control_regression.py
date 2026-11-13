#!/usr/bin/env python3
"""Compile production control Actions, selectors, factories and group-heal policy.

World/native spell validation are bounded doubles; native fixtures are required
for stun/root/sleep/heal effects. Mutations must fail actual behavioral asserts.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
base = root / 'modules/mod_playerbots/src/strategy'
druid = base / 'Classes/druid'


def block(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def clazz(text, name):
    return block(text, 'class ' + name + ' :') + ';\n'


def without_includes(text):
    return '\n'.join(s for s in text.splitlines() if not s.startswith('#include "')) + '\n'


prefix = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <type_traits>
#include <vector>
using uint8=std::uint8_t; using uint32=std::uint32_t; using int32=std::int32_t;
using ObjectGuid=uint32; using GuidVector=std::vector<ObjectGuid>;
constexpr int EFFECT_0=0, SPELL_CAST_OK=255, SPELL_FAILED_NOT_SHAPESHIFT=1;
constexpr int BOT_STATE_COMBAT=0;
enum { SPELL_AURA_MOD_ROOT, SPELL_AURA_PERIODIC_DAMAGE, SPELL_AURA_PERIODIC_DAMAGE_PERCENT,
       SPELL_AURA_PERIODIC_LEECH, SPELL_AURA_MOD_STUN };
enum CurrentSpellTypes { CURRENT_GENERIC_SPELL, CURRENT_CHANNELED_SPELL };
struct Unit; struct Player;
struct SpellInfo {
    bool positive=false; int shape=0;
    int CheckTarget(Player const*,Unit const*) const;
    int CheckShapeshift(int) const { return shape; }
    bool IsPositive() const { return positive; }
};
struct Spell { SpellInfo* info; SpellInfo const* GetSpellInfo() const { return info; } };
struct Unit {
    bool alive=true, world=true, los=true, attackable=true, assistable=true, immune=false, valid=true, cc=false;
    int map=1, phase=1; float distance=0, health=100; std::set<int> auras;
    Spell* casts[2]={nullptr,nullptr};
    bool IsInWorld() const { return world; } bool IsAlive() const { return alive; }
    int GetMap() const { return map; } int GetMapId() const { return map; }
    bool HasAuraType(int t) const { return auras.count(t); }
    bool HasBreakableByDamageCrowdControlAura() const { return cc; }
    bool IsImmunedToSpellEffect(SpellInfo const*,int) const { return immune; }
    bool IsNonMeleeSpellCasted(bool) const { return casts[0] || casts[1]; }
    Spell* GetCurrentSpell(CurrentSpellTypes t) const { return casts[t]; }
    float GetHealthPct() const { return health; } bool IsFullHealth() const { return health==100; }
};
int SpellInfo::CheckTarget(Player const*, Unit const* u) const { return u->valid ? SPELL_CAST_OK : 7; }
struct GroupReference { Player* p; GroupReference* following=nullptr;
    Player* GetSource(){return p;} GroupReference* next(){return following;} };
struct Group { std::vector<GroupReference> members;
    void Set(std::initializer_list<Player*> list) { members.clear();for(auto p:list)members.push_back({p});
        for(size_t i=1;i<members.size();++i)members[i-1].following=&members[i]; }
    GroupReference* GetFirstMember(){return members.empty()?nullptr:&members[0];} };
struct Player : Unit {
    std::set<uint32> known,buffs; bool flying=false,taxi=false; int form=0;
    Unit* victim=nullptr; Group* group=nullptr;
    bool HasSpell(uint32 id) const { return known.count(id); } bool HasAura(uint32 id) const{return buffs.count(id);}
    bool IsFlying()const{return flying;} bool IsInFlight()const{return taxi;}
    bool IsInMap(Unit const* u)const{return map==u->map;}
    bool InSamePhase(Unit const* u)const{return phase==u->phase;}
    bool IsValidAttackTarget(Unit const* u)const{return u->attackable;}
    bool IsValidAssistTarget(Unit const* u)const{return u->assistable && InSamePhase(u);}
    bool IsWithinLOSInMap(Unit const* u)const{return u->los;}
    bool IsWithinMeleeRange(Unit const* u)const{return u->distance<=5;}
    float GetDistance(Unit const* u)const{return u->distance;}
    float GetExactDist(Unit const* u)const{return u->distance;}
    float GetSpellMaxRangeForTarget(Unit const*,SpellInfo const*)const{return 30;}
    Unit* GetVictim()const{return victim;} int GetShapeshiftForm()const{return form;}
    Group* GetGroup()const{return group;}
};
struct Config { float spellDistance=30,healDistance=40,sightDistance=60,criticalHealth=20,
    lowHealth=40,mediumHealth=60,almostFullHealth=90; } config;
auto sPlayerbotAIConfig=&config;
struct Manager { SpellInfo info; bool present=true; SpellInfo const* GetSpellInfo(uint32){return present?&info:nullptr;} } manager;
auto sSpellMgr=&manager;
template<class T> struct Value { T value{}; std::function<T()> calculate;
    T Get(){return calculate?calculate():value;} };
struct Action;
struct Context { Value<Unit*> current; Value<GuidVector> attackers; Value<uint8> count;
    std::map<std::string,Action*> actions;
    std::function<uint8(std::string const&)> healCount;
    template<class T> Value<T>* GetValue(std::string const&,std::string const& q="") {
        if constexpr(std::is_same_v<T,Unit*>)return &current;
        else if constexpr(std::is_same_v<T,GuidVector>)return &attackers;
        else { count.value=healCount?healCount(q):count.value;return &count; } }
    Action* GetAction(std::string const& n){return actions.count(n)?actions.at(n):nullptr;} };
struct PlayerbotAI { Player* bot; Context context; Unit* marked=nullptr;
    bool canCast=true, castResult=true, emergency=false, healingStrategy=true; int casts=0; std::string spell; Unit* target=nullptr;
    bool HasStrategy(std::string const& name,int){return name=="heal" && healingStrategy;}
    std::map<ObjectGuid,Unit*> units; std::set<Unit*> rejuvenated,shielded;
    Player* GetBot(){return bot;} Context* GetAiObjectContext(){return &context;}
    Unit* GetUnit(ObjectGuid id){return units.count(id)?units.at(id):nullptr;}
    bool CanCastSpell(std::string const&,Unit*){return canCast;}
    bool HasAura(char const*,Unit* u){return rejuvenated.count(u);}
    bool HasAnyAuraOf(Unit* u,char const*,char const*,std::nullptr_t){return shielded.count(u);}
    int32 GetNearGroupMemberCount(float dis=sPlayerbotAIConfig->sightDistance);
};
struct RtiCcTargetValue { PlayerbotAI* ai; RtiCcTargetValue(PlayerbotAI* ai):ai(ai){}
    Unit* Calculate(){return ai->marked;} };
struct Event {};
struct NextAction { std::string name; NextAction(std::string n):name(n){}
    static NextAction** array(int,NextAction* a,std::nullptr_t){return new NextAction*[2]{a,nullptr};}
    static void destroy(NextAction** a){if(a){delete a[0];delete[] a;}} };
struct Action { PlayerbotAI* botAI; Player* bot; Context* context; std::string name;
    Action(PlayerbotAI* ai,std::string n):botAI(ai),bot(ai->bot),context(&ai->context),name(n){}
    virtual ~Action()=default; virtual std::string const getName(){return name;}
    virtual Unit* GetTarget(){return context->current.Get();}
    virtual bool isUseful(){return GetTarget();} virtual bool isPossible(){return botAI->canCast;}
    virtual bool Execute(Event){++botAI->casts;botAI->spell=name;botAI->target=GetTarget();return botAI->castResult;}
    virtual NextAction** getPrerequisites(){return nullptr;} };
struct CastSpellAction : Action { using Action::Action; };
enum class HealingManaEfficiency { VERY_HIGH, HIGH };
struct HealPartyMemberAction : CastSpellAction {
    HealPartyMemberAction(PlayerbotAI* ai,std::string n,float,HealingManaEfficiency):CastSpellAction(ai,n){} };
struct Trigger { PlayerbotAI* botAI;Player* bot;Context* context;std::string name;
    Trigger(PlayerbotAI* ai,std::string n):botAI(ai),bot(ai->bot),context(&ai->context),name(n){}
    virtual ~Trigger()=default;virtual bool IsActive(){return false;} };
struct PartyMemberCriticalHealthTrigger {PlayerbotAI* ai;PartyMemberCriticalHealthTrigger(PlayerbotAI* ai):ai(ai){}
    bool IsActive(){return ai->emergency;} };
template<class T>struct NamedObjectContext {std::map<std::string,T*(*)(PlayerbotAI*)> creators;
    T* create(std::string n,PlayerbotAI* ai){return creators.count(n)?creators.at(n)(ai):nullptr;} };
struct AoeHealValue {Player* bot;std::string qualifier;uint8 Calculate();};
struct MinValueCalculator {float minValue;void* param=nullptr;MinValueCalculator(float v):minValue(v){}
    void probe(float v,void* p){if(v<minValue){minValue=v;param=p;}}};
#define AI_VALUE2(T,n,q) context->GetValue<T>(n,q)->Get()
'''

native = without_includes((druid / 'DruidControlActions.h').read_text())
native += without_includes((druid / 'DruidControlActions.cpp').read_text())
context = (druid / 'DruidAiObjectContext.cpp').read_text()
assert 'triggerContexts.Add(new DruidControlTriggerFactoryInternal());' in context
native += clazz(context, 'DruidControlTriggerFactoryInternal')
for filename, names in [('DruidActions.h', ['CastEntanglingRootsCcAction', 'CastHibernateCcAction', 'CastRejuvenationOnNotFullAction']),
                        ('DruidBearActions.h', ['CastBashAction', 'CastBashOnEnemyHealerAction'])]:
    for name in names:
        native += clazz((druid / filename).read_text(), name)
for sig in ['Unit* CastRejuvenationOnNotFullAction::GetTarget()', 'bool CastRejuvenationOnNotFullAction::isUseful()',
            'bool CastRejuvenationOnNotFullAction::Execute(']:
    native += block((druid / 'DruidActions.cpp').read_text(), sig)
native += clazz((base / 'triggers/HealthTriggers.h').read_text(), 'AoeInGroupTrigger')
native += block((base / 'triggers/HealthTriggers.cpp').read_text(), 'bool AoeInGroupTrigger::IsActive()')
native += block((base / 'value/AoeHealValue.cpp').read_text(), 'uint8 AoeHealValue::Calculate()')
native += block((root / 'modules/mod_playerbots/src/AI/PlayerbotAI.cpp').read_text(), 'int32 PlayerbotAI::GetNearGroupMemberCount(')
common = (base / 'triggers/TriggerContext.h').read_text()
native += 'class TriggerContext : public NamedObjectContext<Trigger> { public: TriggerContext() {\n'
native += '\n'.join(line for line in common.splitlines() if 'creators["group heal setting"]' in line or 'creators["medium group heal setting"]' in line)
native += '\n}\n'
native += block(common, '    static Trigger* group_heal_setting(')
native += block(common, '    static Trigger* medium_group_heal_setting(') + '};\n'
priest = base / 'Classes/priest'
for name in ('CastPowerWordShieldOnNotFullAction', 'CastPowerWordShieldOnAlmostFullHealthBelowAction'):
    native += clazz((priest / 'PriestActions.h').read_text(), name)
    for sig in ('Unit* '+name+'::GetTarget()', 'bool '+name+'::isUseful()', 'bool '+name+'::Execute('):
        native += block((priest / 'PriestActions.cpp').read_text(), sig)

tests = r'''
int main() {
    Player bot; bot.known={339,2637,5211,132158}; PlayerbotAI ai{&bot};
    Unit enemy,other; ai.marked=&enemy;
    CastEntanglingRootsCcAction roots(&ai); CastHibernateCcAction sleep(&ai);
    CastBashAction bash(&ai); CastBashOnEnemyHealerAction healer(&ai);
    ai.context.actions={{"entangling roots on cc",&roots},{"hibernate on cc",&sleep},{"bash",&bash},{"bash on enemy healer",&healer}};
    DruidControlTriggerFactoryInternal factory;
    auto active=[&](std::string name){Trigger* t=factory.create(name,&ai);assert(t);bool v=t->IsActive();delete t;return v;};
    assert(active("entangling roots") && active("hibernate"));
    assert(roots.Execute({}) && ai.spell=="entangling roots" && ai.target==&enemy);
    assert(sleep.Execute({}) && ai.spell=="hibernate");
    for(bool* flag:{&enemy.alive,&enemy.world,&enemy.attackable,&enemy.los,&enemy.valid}) {
        *flag=false;assert(!active("hibernate") && !sleep.Execute({}));*flag=true; }
    enemy.immune=true;assert(!roots.GetTarget());enemy.immune=false;
    enemy.map=2;assert(!roots.GetTarget());enemy.map=1;
    enemy.phase=2;assert(!roots.GetTarget());enemy.phase=1;
    enemy.distance=31;assert(!roots.GetTarget());enemy.distance=30;assert(roots.GetTarget());enemy.distance=0;
    enemy.cc=true;assert(!roots.GetTarget());enemy.cc=false;
    for(int aura:{SPELL_AURA_MOD_ROOT,SPELL_AURA_PERIODIC_DAMAGE,SPELL_AURA_PERIODIC_DAMAGE_PERCENT,SPELL_AURA_PERIODIC_LEECH}) {
        enemy.auras.insert(aura);assert(!sleep.GetTarget());enemy.auras.clear(); }
    ai.context.current.value=&enemy;assert(!roots.GetTarget());ai.context.current.value=nullptr;
    bot.victim=&enemy;assert(!roots.GetTarget());bot.victim=nullptr;
    ai.marked=nullptr;assert(!roots.Execute({}));ai.marked=&other;assert(roots.GetTarget()==&other);ai.marked=&enemy;
    for(bool* flag:{&bot.flying,&bot.taxi}){*flag=true;assert(!active("entangling roots")&&!roots.getPrerequisites());*flag=false;}
    bot.known.erase(339);assert(!roots.GetTarget());bot.known.insert(339);
    manager.info.shape=SPELL_FAILED_NOT_SHAPESHIFT;auto p=roots.getPrerequisites();assert(p&&p[0]->name=="caster form");NextAction::destroy(p);
    manager.info.shape=0;assert(!roots.getPrerequisites());
    ai.canCast=false;assert(!active("entangling roots")&&!roots.Execute({}));ai.canCast=true;
    ai.castResult=false;assert(!roots.Execute({}));ai.castResult=true;
    assert(!active("bash"));ai.context.current.value=&enemy;assert(!active("bash"));
    SpellInfo positive;positive.positive=true;Spell cast{&positive};enemy.casts[0]=&cast;
    assert(active("bash")&&bash.Execute({})&&ai.spell=="mighty bash");
    enemy.distance=6;assert(!active("bash"));enemy.distance=0;
    enemy.immune=true;assert(!active("bash"));enemy.immune=false;
    enemy.auras.insert(SPELL_AURA_MOD_STUN);assert(!active("bash"));enemy.auras.clear();
    bot.known.erase(5211);assert(!active("bash"));bot.known.insert(5211);
    ai.context.attackers.value={7,8};ai.units={{7,&enemy},{8,&other}};other.casts[1]=&cast;
    assert(active("bash on enemy healer")&&healer.GetTarget()==&other&&healer.Execute({}));
    positive.positive=false;assert(!active("bash on enemy healer"));positive.positive=true;
    other.casts[1]=nullptr;assert(!healer.Execute({}));
    assert(!active("nature's swiftness"));ai.emergency=true;assert(active("nature's swiftness"));
    ai.healingStrategy=false;assert(!active("nature's swiftness"));ai.healingStrategy=true;
    bot.buffs.insert(132158);assert(!active("nature's swiftness"));bot.buffs.clear();
    bot.known.erase(132158);assert(!active("nature's swiftness"));bot.known.insert(132158);
    ai.canCast=false;assert(!active("nature's swiftness"));ai.canCast=true;

    CastRejuvenationOnNotFullAction rejuv(&ai); assert(!rejuv.GetTarget()&&!rejuv.Execute({}));
    assert(rejuv.getName()=="rejuvenation on not full");
    Player a,b,c,d;Group group;group.Set({nullptr,&bot,&a,&b,&c,&d});bot.group=&group;
    a.health=10;b.health=20;c.health=50;d.health=80;
    assert(rejuv.GetTarget()==&a);
    for(bool* flag:{&a.alive,&a.world,&a.assistable,&a.los}){*flag=false;assert(rejuv.GetTarget()==&b);*flag=true;}
    a.map=2;assert(rejuv.GetTarget()==&b);a.map=1;a.phase=2;assert(rejuv.GetTarget()==&b);a.phase=1;
    a.distance=31;assert(rejuv.GetTarget()==&b);a.distance=0;
    ai.rejuvenated.insert(&a);assert(rejuv.GetTarget()==&b);ai.rejuvenated.clear();
    assert(rejuv.Execute({})&&ai.target==&a&&ai.spell=="rejuvenation");
    ai.castResult=false;assert(!rejuv.Execute({}));ai.castResult=true;
    bot.group=nullptr;assert(!rejuv.Execute({}));bot.group=&group;

    AoeHealValue value{&bot,"medium"}; ai.context.healCount=[&](std::string q){value.qualifier=q;return value.Calculate();};
    TriggerContext shared;
    Trigger* light=shared.create("group heal setting",&ai);Trigger* medium=shared.create("medium group heal setting",&ai);
    assert(light&&medium&&light->IsActive()&&medium->IsActive());
    c.health=80;assert(light->IsActive()&&!medium->IsActive());
    a.health=b.health=c.health=d.health=100;assert(!light->IsActive());
    a.health=b.health=c.health=50;assert(light->IsActive());
    c.los=false;assert(!light->IsActive());c.los=true;
    group.Set({&bot,&a,&b,&c});assert(!light->IsActive());
    group.Set({&bot,&a,&b,&c,&d});assert(light->IsActive());
    bot.group=nullptr;assert(!light->IsActive());delete light;delete medium;
    CastPowerWordShieldOnNotFullAction shield(&ai);
    CastPowerWordShieldOnAlmostFullHealthBelowAction firstShield(&ai);
    assert(!shield.GetTarget()&&!firstShield.GetTarget()&&!shield.Execute({})&&!firstShield.Execute({}));
    bot.group=&group;group.Set({nullptr,&bot,&a,&b,&c,&d});
    a.health=80;b.health=20;c.health=50;d.health=100;
    assert(shield.GetTarget()==&b && firstShield.GetTarget()==&a);
    assert(shield.getName()=="power word: shield on not full");
    assert(firstShield.getName()=="power word: shield on almost full health below");
    for(bool* flag:{&b.alive,&b.world,&b.assistable,&b.los}){*flag=false;assert(shield.GetTarget()==&c);*flag=true;}
    b.map=2;assert(shield.GetTarget()==&c);b.map=1;
    b.phase=2;assert(shield.GetTarget()==&c);b.phase=1;
    b.distance=31;assert(shield.GetTarget()==&c);b.distance=0;
    ai.shielded.insert(&b);assert(shield.GetTarget()==&c);ai.shielded.clear();
    assert(shield.Execute({})&&ai.spell=="power word: shield"&&ai.target==&b);
    a.health=95;assert(firstShield.GetTarget()==&b);a.health=80;
    a.los=false;assert(firstShield.GetTarget()==&b);a.los=true;
    ai.shielded.insert(&a);assert(firstShield.GetTarget()==&b);ai.shielded.clear();
    ai.castResult=false;assert(!shield.Execute({})&&!firstShield.Execute({}));ai.castResult=true;
    bot.group=nullptr;assert(!shield.Execute({})&&!firstShield.Execute({}));
    std::cout<<"PASS: Druid control/Swift contracts, live target selection, shared healing mappings\n";
}
'''

mutations = [
    ('missing CC trigger', 'creators["hibernate"] = &hibernate;', ''),
    ('wrong CC spell alias', ': DruidCcAction(botAI, "hibernate", 2637, "hibernate on cc")', ': DruidCcAction(botAI, "hibernate on cc", 2637, "hibernate on cc")'),
    ('ignore creature contract', 'info->CheckTarget(bot, target) == SPELL_CAST_OK', 'true'),
    ('break CC', 'target->HasBreakableByDamageCrowdControlAura()', 'false'),
    ('flight unshift', '!bot->IsFlying() && !bot->IsInFlight()', 'true'),
    ('ignore Bash immunity', '!target->IsImmunedToSpellEffect(info, EFFECT_0)', 'true'),
    ('wrong Bash spell', 'CastSpellAction(ai, "mighty bash")', 'CastSpellAction(ai, "bash")'),
    ('Swift no emergency', '&& critical.IsActive()', ''),
    ('Swift without follow-up strategy', 'botAI->HasStrategy("heal", BOT_STATE_COMBAT) &&', ''),
    ('group null dereference', 'if (!group)\n        return nullptr;', ''),
    ('wrong group health tier', '"group heal setting", "almost full"', '"group heal setting", "medium"'),
    ('ignore Rejuvenation instance', 'player->GetMap() != bot->GetMap() ||', ''),
    ('Priest null group', 'Unit* CastPowerWordShieldOnNotFullAction::GetTarget()\n{\n    Group* group = bot->GetGroup();\n    if (!group)\n        return nullptr;',
     'Unit* CastPowerWordShieldOnNotFullAction::GetTarget()\n{\n    Group* group = bot->GetGroup();'),
    ('Priest weakened-soul/shield exclusion', 'botAI->HasAnyAuraOf(player, "weakened soul", "power word: shield", nullptr)', 'false'),
]
with tempfile.TemporaryDirectory(prefix='loa-druid-control-') as temp:
    cpp=Path(temp)/'test.cpp';binary=Path(temp)/'test'
    def run(source, label, failure=False):
        cpp.write_text(prefix+source+tests)
        result=subprocess.run([sys.argv[2],'-std=c++20','-O1','-g','-fsanitize=address,undefined',
            '-fno-omit-frame-pointer',str(cpp),'-o',str(binary)],capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError(label+' compile failed:\n'+result.stderr)
        result=subprocess.run([str(binary)],capture_output=True,text=True,env=dict(os.environ,
            ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1'))
        if failure:
            assert result.returncode, 'mutation survived: '+label
            print('rejected:',label)
        else:
            assert result.returncode==0, result.stdout+result.stderr
            print(result.stdout.strip())
    run(native,'baseline')
    if '--verify-mutations' in sys.argv:
        for label,old,new in mutations:
            assert old in native, (label,old)
            run(native.replace(old,new,1),label,True)
