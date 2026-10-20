#!/usr/bin/env python3
"""Actual diagnostic adapter against controlled spellbook/AI/native metadata APIs."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"
production = (module / "BotLifeAbilities.cpp").read_text()
# Probes must not cast, consume spell-mod charges, draw damage RNG or alter gameplay.
for forbidden in ("CalcPowerCost(", "CalcValue(", "CalculateSpellDamage(", "ApplySpellMod(",
                  "CanCastSpell(", "CastSpell(", "DoSpecificAction(", "SetPower(", "SetHealth(",
                  "AddAura(", "RemoveAura(", "TeleportTo(", "CharacterDatabase"):
    assert forbidden not in production, forbidden
native_info = (root / "src/server/game/Spells/SpellInfo.cpp").read_text()
assert "Effects[i] = SpellEffectInfo(this, i," in native_info
executor = (module / "BotLifeQuestExecutor.cpp").read_text()
assert executor.count("LogEnhancementAbilities(ai)") == 1
assert executor.index("LogEnhancementAbilities(ai)") < executor.index("ActivityResult Update(")

mocks = r'''
#include "BotLifeAbilities.h"
#include <array>
#include <map>
#include <set>
#include <string>
#include <cassert>
#include <utility>
using uint32=uint32_t;
constexpr uint32 CLASS_SHAMAN=7, SPEC_SHAMAN_ENHANCEMENT=263, PLAYERSPELL_REMOVED=2;
constexpr uint32 BASE_ATTACK=0, OFF_ATTACK=1, BOT_STATE_COMBAT=1, POWER_MANA=0;
template<class... T> void Log(char const*, char const*, T const&...) {}
#define TC_LOG_INFO(...) Log(__VA_ARGS__)
struct Power { uint32 PowerType=0,Cost=20; float CostPercentage=5; uint32 RequiredAura=0; };
struct Effect {
    uint32 Effect=0,ApplyAuraName=0,TriggerSpell=0; int BasePoints=0,DieSides=0;
    float ScalingMultiplier=0,BonusMultiplier=0; bool area=false;
    bool IsEffect() const { return Effect!=0; }
    bool IsTargetingArea() const { return area; }
};
struct SpellInfo {
    uint32 Id=0,StartRecoveryTime=1500; bool passive=false;
    uint32 cast=0,recovery=8000; std::array<Effect,3> Effects;
    std::vector<Power const*> SpellPowers;
    bool IsPassive() const { return passive; }
    uint32 GetSchoolMask() const { return 4; }
    uint32 CalcCastTime(uint32) const { return cast; }
    uint32 GetRecoveryTime() const { return recovery; }
    void GetEffects() const = delete; // Not initialized in this fork; never use it.
};
struct Manager {
    std::map<uint32,SpellInfo> spells;
    SpellInfo const* GetSpellInfo(uint32 id) const {
        auto it=spells.find(id); return it==spells.end()?nullptr:&it->second;
    }
} manager;
auto* sSpellMgr=&manager;
struct Known { uint32 state=0; bool active=true,disabled=false; };
struct Guid { uint32 GetCounter() const { return 584; } };
struct Player {
    uint32 cls=CLASS_SHAMAN,spec=SPEC_SHAMAN_ENHANCEMENT;
    bool dual=true,main=true,off=true,mainAllowed=true,offAllowed=true;
    std::map<uint32,Known*> spells; std::map<uint32,uint32> cooldown;
    std::set<uint32> auras;
    uint32 GetClass() const { return cls; }
    uint32 GetTalentSpecialization() const { return spec; }
    auto const& GetSpellMap() const { return spells; }
    bool CanUseAttackType(uint32 attack) const { return attack==OFF_ATTACK?offAllowed:mainAllowed; }
    void const* GetWeaponForAttack(uint32 attack,bool usable) const {
        assert(usable); return (attack==OFF_ATTACK?off:main)?this:nullptr;
    }
    bool CanDualWield() const { return dual; }
    bool HasSpellCooldown(uint32 id) const { return GetSpellCooldownDelay(id)>0; }
    uint32 GetSpellCooldownDelay(uint32 id) const {
        auto it=cooldown.find(id); return it==cooldown.end()?0:it->second;
    }
    uint32 GetLevel() const { return 56; }
    bool HasAura(uint32 id) const { return auras.count(id); }
    Guid GetGUID() const { return {}; }
    int GetPower(uint32) const { return 800; }
    int GetMaxPower(uint32) const { return 1000; }
    uint32 GetCreateMana() const { return 600; }
};
struct Value { uint32 value=0; uint32 Get() const { return value; } };
struct AiObjectContext {
    std::map<std::string,Value> values; uint32 calls=0;
    std::set<std::string> actions,triggers;
    void const* GetAction(std::string const& name) const { return actions.count(name)?this:nullptr; }
    void const* GetTrigger(std::string const& name) const { return triggers.count(name)?this:nullptr; }
    template<class T> Value* GetValue(char const* name,char const* action) {
        assert(std::string(name)=="spell id"); ++calls;
        auto it=values.find(action); return it==values.end()?nullptr:&it->second;
    }
};
struct PlayerbotAI {
    Player* bot=nullptr; AiObjectContext* context=nullptr; bool melee=true;
    Player* GetBot() { return bot; }
    AiObjectContext* GetAiObjectContext() { return context; }
    bool HasStrategy(char const* name,uint32 state) {
        assert(std::string(name)=="melee" && state==BOT_STATE_COMBAT); return melee;
    }
};
'''

tests = r'''
int main() {
    using namespace BotLife;
    Player bot; AiObjectContext context; PlayerbotAI ai{&bot,&context};
    assert(ReadEnhancementAbilities(ai).size()==12);
    assert(context.calls==12);
    context.actions={"stormstrike","lightning bolt","fire elemental totem melee"};
    context.triggers={"fire elemental totem"};
    Known known;
    bot.spells[17364]=&known;
    context.values["stormstrike"]={17364};
    context.values["lava lash"]={60103};
    context.values["lightning bolt"]={403};
    SpellInfo parent; parent.Id=17364;
    parent.Effects[0]={64,0,32175,0,0,0,0,false};
    parent.Effects[1]={64,0,17364,0,0,0,0,false}; // Self cycle.
    SpellInfo child; child.Id=32175;
    child.Effects[0]={31,0,17364,450,0,0.5f,0,false}; // Back edge.
    Power power; Power alternate; alternate.RequiredAura=123;
    parent.SpellPowers={&power,nullptr,&alternate};
    manager.spells[17364]=parent; manager.spells[32175]=child;
    SpellInfo bolt; bolt.Id=403; bolt.cast=2500; manager.spells[403]=bolt;
    auto s=ReadEnhancementAbilities(ai);
    assert(s[0].baseKnown && s[0].active && !s[0].disabled && !s[0].passive);
    assert(s[0].meleeStrategy && s[0].weaponReady && s[0].cooldownReady);
    assert(s[0].actionRegistered && !s[0].triggerRegistered);
    assert(s[6].actionRegistered && !s[6].triggerRegistered);
    assert(std::string(s[6].trigger)=="maelstrom weapon 4");
    assert(s[11].actionRegistered && s[11].triggerRegistered);
    assert(!s[1].actionRegistered);
    assert(s[0].baseRecoveryMs==8000 && s[0].baseGcdMs==1500);
    assert(s[0].effects.size()==3 && s[0].effects[2].spell==32175);
    assert(s[0].effects[2].base==450 && s[0].effects[2].scaling==0.5f);
    assert(s[0].powers.size()==2 && s[0].powers[0].flat==20 && s[0].powers[0].percent==5);
    assert(!s[0].powers[1].auraPresent);
    assert(s[6].baseCastMs==2500 && !s[6].active); // Resolver alone is not knowledge.
    assert(std::string(s[6].condition)=="maelstrom-weapon-4-trigger");
    bot.auras.insert(123); bot.cooldown[17364]=7000;
    known.disabled=true; ai.melee=false; bot.mainAllowed=false; bot.off=false;
    s=ReadEnhancementAbilities(ai);
    assert(s[0].disabled && !s[0].meleeStrategy && !s[0].weaponReady);
    assert(!s[0].cooldownReady && s[0].cooldownMs==7000 && s[0].powers[1].auraPresent);
    assert(!s[4].weaponReady);
    bot.off=true; bot.offAllowed=false;
    assert(!ReadEnhancementAbilities(ai)[4].weaponReady);
    bot.offAllowed=true; bot.dual=false;
    assert(!ReadEnhancementAbilities(ai)[4].weaponReady);
    known.state=PLAYERSPELL_REMOVED;
    s=ReadEnhancementAbilities(ai); assert(!s[0].baseKnown && !s[0].active);
    known.state=0; known.active=false; manager.spells[17364].passive=true;
    s=ReadEnhancementAbilities(ai); assert(s[0].baseKnown && !s[0].active && s[0].passive);
    manager.spells.erase(17364);
    s=ReadEnhancementAbilities(ai); assert(s[0].effects.empty() && !s[0].cooldownReady);
    LogEnhancementAbilities(ai); // Actual logger paths compile with typed arguments.
    uint32 calls=context.calls; bot.spec=262;
    assert(ReadEnhancementAbilities(ai).empty() && context.calls==calls);
    bot.spec=263; bot.cls=1;
    assert(ReadEnhancementAbilities(ai).empty() && context.calls==calls);
    bot.cls=7; ai.bot=nullptr; assert(ReadEnhancementAbilities(ai).empty());
    ai.bot=&bot; ai.context=nullptr; assert(ReadEnhancementAbilities(ai).empty());
    assert(bot.GetPower(POWER_MANA)==800 && bot.spells.size()==1 && bot.cooldown[17364]==7000);
}
'''
body = "\n".join(line for line in production.splitlines() if not line.startswith("#include"))
with tempfile.TemporaryDirectory(prefix="loa-abilities-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(mocks + body + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(module),
                    str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife read-only Enhancement ability snapshots passed")
