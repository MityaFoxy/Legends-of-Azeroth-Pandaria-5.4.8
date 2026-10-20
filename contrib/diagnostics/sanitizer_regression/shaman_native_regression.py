#!/usr/bin/env python3
"""Actual shaman trigger/actions, item-target binding and aura-save predicate."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
shaman = root / "modules/mod_playerbots/src/strategy/Classes/shaman"


def body(text):
    return "\n".join(line for line in text.splitlines() if not line.startswith("#"))


def block(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


header = (shaman / "ShamanActions.h").read_text()
actions = (shaman / "ShamanActions.cpp").read_text()
factory = block((shaman / "ShamanAiObjectContext.cpp").read_text(),
                "class ShamanATriggerFactoryInternal") + ";"
ai = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.cpp").read_text()
cast = block(ai, "bool PlayerbotAI::CastSpell(uint32 spellId, Unit* target, Item* itemTarget)")
binding = block(cast, "if (itemTarget || (spellInfo->Targets & TARGET_FLAG_ITEM))")
assert "targets.SetItemTarget(itemTarget)" in binding and "m_CastItem" not in binding
assert "TRIGGERED_NONE" in cast and "spell->prepare(&targets)" in cast
assert "item for spell" not in actions[:actions.index("bool CastTotemAction")]
assert "BotLife" not in (shaman / "ShamanTriggers.cpp").read_text()
assert factory.count('creators["') == 3  # No AoE or Flame Shock activation in this increment.
aura_save = block((root / "src/server/game/Spells/Auras/SpellAuras.cpp").read_text(),
                  "bool Aura::CanBeSaved() const")
assert "GetEffects()" not in aura_save and "GetSpellInfo()->Effects" in aura_save

mocks = r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <map>
#include <set>
#include <array>
using uint32=uint32_t;
enum WeaponAttackType { BASE_ATTACK, OFF_ATTACK, RANGED_ATTACK };
constexpr uint32 CLASS_SHAMAN=7, SPEC_SHAMAN_ENHANCEMENT=263, TEMP_ENCHANTMENT_SLOT=1;
constexpr uint32 TARGET_FLAG_ITEM=16;
struct Item {
    uint32 enchant=0,owner=1; bool usable=true;
    uint32 GetEnchantmentId(uint32 slot) const { assert(slot==TEMP_ENCHANTMENT_SLOT); return enchant; }
    uint32 GetOwnerGUID() const { return owner; }
};
struct ProcAura { uint32 stacks=0; uint32 GetStackAmount() const { return stacks; } };
using Aura=ProcAura;
struct Player {
    uint32 cls=7,spec=263,selection=2; bool alive=true,trade=false,dual=true,mainAllowed=true,offAllowed=true;
    Item main,off; bool hasMain=true,hasOff=true;
    std::set<uint32> known{8232,8024,403}; ProcAura aura; bool proc=false;
    uint32 GetClass() const { return cls; }
    uint32 GetTalentSpecialization() const { return spec; }
    bool IsAlive() const { return alive; }
    void* GetTradeData() const { return trade?(void*)this:nullptr; }
    bool CanDualWield() const { return dual; }
    bool CanUseAttackType(WeaponAttackType hand) const { return hand==BASE_ATTACK?mainAllowed:offAllowed; }
    Item* GetWeaponForAttack(WeaponAttackType hand,bool usable) {
        assert(usable);
        Item* item=hand==BASE_ATTACK?(hasMain?&main:nullptr):(hasOff?&off:nullptr);
        return item && item->usable ? item : nullptr;
    }
    bool HasSpell(uint32 spell) const { return known.count(spell); }
    ProcAura const* GetAura(uint32 id) const { assert(id==53817); return proc?&aura:nullptr; }
    uint32 GetGUID() const { return 1; }
    void SetSelection(uint32 id) { selection=id; }
};
struct PlayerbotAI {
    Player* bot; bool vehicle=false,possible=true,castResult=true; Item* checked=nullptr; Item* castItem=nullptr;
    int casts=0;
    bool IsInVehicle() const { return vehicle; }
    bool CanCastSpell(std::string const&,Player* target,Item* item) {
        assert(target==bot); checked=item; return possible;
    }
    bool CastSpell(std::string const&,Player* target,Item* item) {
        assert(target==bot); castItem=item; ++casts; return castResult;
    }
};
struct Event {};
struct CastSpellAction {
    PlayerbotAI* botAI; Player* bot; std::string spell;
    CastSpellAction(PlayerbotAI* ai,std::string name):botAI(ai),bot(ai->bot),spell(name) {}
    virtual ~CastSpellAction()=default;
    virtual bool isPossible() { return false; } virtual bool isUseful() { return false; }
    virtual bool Execute(Event) { return false; }
    virtual std::string const GetTargetName() { return ""; }
};
struct Trigger {
    Player* bot;
    Trigger(PlayerbotAI* ai,std::string const&):bot(ai->bot) {}
    virtual ~Trigger()=default;
    virtual bool IsActive() { return false; }
};
template<class T> struct NamedObjectContext {
    std::map<std::string,T*(*)(PlayerbotAI*)> creators;
};
'''
native = body((shaman / "ShamanWeaponImbue.cpp").read_text())
native += body((shaman / "ShamanTriggers.h").read_text())
native += body((shaman / "ShamanTriggers.cpp").read_text())
native += header[header.index("class CastShamanWeaponImbueAction"):header.index("class CastTotemAction")]
native += body(actions[:actions.index("bool CastTotemAction")])
native += factory
binding_mocks = r'''
int liveSpells=0;
struct Spell { Item* m_CastItem=nullptr; Spell(){++liveSpells;} ~Spell(){--liveSpells;} };
struct SpellInfo { uint32 Targets=0; };
struct Targets {
    Item* item=nullptr; void SetItemTarget(Item* p) { item=p; }
};
bool Bind(Player* bot,SpellInfo const* spellInfo,Item* itemTarget,Targets& targets) {
    uint32 oldSel=bot->selection; bot->selection=99;
    Spell* spell=new Spell;
'''
binding_mocks += binding + r'''
    assert(!spell->m_CastItem); delete spell; bot->SetSelection(oldSel); return true;
}
'''
tests = r'''
int main() {
    Player bot; PlayerbotAI ai{&bot};
    ShamanATriggerFactoryInternal factory;
    Trigger* main=factory.creators.at("main hand weapon no imbue")(&ai);
    Trigger* off=factory.creators.at("off hand weapon no imbue")(&ai);
    Trigger* proc=factory.creators.at("maelstrom weapon 4")(&ai);
    assert(main->IsActive() && off->IsActive() && !proc->IsActive());
    for(uint32 stacks=0;stacks<=5;++stacks) {
        bot.proc=true; bot.aura.stacks=stacks; assert(proc->IsActive()==(stacks>=4));
    }
    bot.known.erase(403); assert(!proc->IsActive()); bot.known.insert(403);
    CastWindfuryWeaponAction wind(&ai); CastFlametongueWeaponAction flame(&ai);
    assert(wind.isUseful() && wind.isPossible() && ai.checked==&bot.main);
    assert(wind.Execute({}) && ai.castItem==&bot.main && ai.casts==1);
    assert(flame.isPossible() && ai.checked==&bot.off);
    assert(flame.Execute({}) && ai.castItem==&bot.off && ai.casts==2);
    // Preserve every existing enchant, even an unexpected one.
    bot.main.enchant=999; bot.off.enchant=5;
    assert(!main->IsActive() && !off->IsActive() && !wind.isUseful() && !flame.Execute({}));
    assert(ai.casts==2);
    bot.main.enchant=bot.off.enchant=0;
    bot.main.usable=false; bot.off.usable=false;
    assert(!main->IsActive() && !off->IsActive() && !wind.isPossible());
    bot.main.usable=bot.off.usable=true;
    bot.mainAllowed=false; bot.offAllowed=false;
    assert(!main->IsActive() && !off->IsActive());
    bot.mainAllowed=bot.offAllowed=true; bot.dual=false;
    assert(main->IsActive() && !off->IsActive()); bot.dual=true;
    bot.hasMain=false; bot.hasOff=false;
    assert(!main->IsActive() && !off->IsActive()); bot.hasMain=bot.hasOff=true;
    bot.trade=true; assert(!main->IsActive() && !wind.Execute({})); bot.trade=false;
    bot.alive=false; assert(!main->IsActive() && !off->IsActive() && !proc->IsActive()); bot.alive=true;
    ai.vehicle=true; assert(!wind.isUseful() && !wind.isPossible() && !wind.Execute({})); ai.vehicle=false;
    ai.possible=false; assert(!flame.isPossible()); ai.possible=true;
    ai.castResult=false; assert(!flame.Execute({})); ai.castResult=true;
    bot.known.erase(8232); assert(!main->IsActive()); bot.known.insert(8232);
    bot.known.erase(8024); assert(!off->IsActive()); bot.known.insert(8024);
    bot.spec=262;
    assert(!main->IsActive() && !off->IsActive() && !proc->IsActive());
    assert(flame.Execute({}) && ai.castItem==&bot.main); // Caster Flametongue still mainhand.
    bot.cls=1; assert(!flame.isUseful()); bot.cls=7; bot.spec=263;
    assert(!GetShamanImbueWeapon(bot,RANGED_ATTACK));
    delete main; delete off; delete proc;
    SpellInfo info; Targets targets;
    assert(Bind(&bot,&info,&bot.off,targets) && targets.item==&bot.off && bot.selection==2);
    info.Targets=TARGET_FLAG_ITEM; targets.item=nullptr;
    assert(!Bind(&bot,&info,nullptr,targets) && !targets.item && bot.selection==2);
    Item foreign; foreign.owner=2;
    assert(!Bind(&bot,&info,&foreign,targets) && !targets.item && bot.selection==2);
    bot.trade=true;
    assert(!Bind(&bot,&info,&bot.main,targets) && !targets.item); bot.trade=false;
    assert(Bind(&bot,&info,&bot.main,targets) && targets.item==&bot.main);
    assert(!liveSpells);
}
'''

aura_mocks = r'''
#include <cassert>
#include <array>
constexpr int SPELL_AURA_CONVERT_RUNE=1,SPELL_AURA_OPEN_STABLE=2,SPELL_AURA_CONTROL_VEHICLE=3;
constexpr int SPELL_ATTR0_CU_DONT_SAVE_AURA_TO_DB=1;
struct SpellEffectInfo {
    bool exists=false,area=false,areaAura=false;
    bool IsEffect() const { return exists; }
    bool IsTargetingArea() const { return area; }
    bool IsAreaAuraEffect() const { return areaAura; }
};
struct SpellInfo {
    std::array<SpellEffectInfo,3> Effects;
    bool channel=false,single=false; int AttributesCu=0;
    auto GetEffects() const = delete;
    bool IsChanneled() const { return channel; }
    bool IsSingleTarget() const { return single; }
};
struct Owner { int GetGUID() const { return 1; } };
struct Aura {
    SpellInfo* m_spellInfo; Owner owner;
    int caster=2,type=0,charges=1; bool passive=false,usesCharges=false;
    bool CanBeSaved() const;
    bool IsPassive() const { return passive; }
    SpellInfo const* GetSpellInfo() const { return m_spellInfo; }
    int GetCasterGUID() const { return caster; }
    Owner const* GetOwner() const { return &owner; }
    bool HasEffectType(int value) const { return type==value; }
    bool IsUsingCharges() const { return usesCharges; }
    int GetCharges() const { return charges; }
};
'''
aura_tests = r'''
int main() {
    SpellInfo spell; Aura aura{&spell};
    assert(aura.CanBeSaved());
    spell.Effects[2]={true,true,false}; assert(!aura.CanBeSaved());
    spell.Effects[2]={true,false,true}; assert(!aura.CanBeSaved());
    spell.Effects[2]={false,true,true}; assert(aura.CanBeSaved());
    spell.Effects[2]={true,true,true}; aura.caster=1; assert(aura.CanBeSaved());
    aura.caster=2; spell.Effects[2]={};
    spell.single=true; assert(!aura.CanBeSaved()); spell.single=false;
    spell.channel=true; assert(!aura.CanBeSaved()); spell.channel=false;
    aura.passive=true; assert(!aura.CanBeSaved()); aura.passive=false;
    for(int type=1;type<=3;++type) { aura.type=type; assert(!aura.CanBeSaved()); }
    aura.type=0; spell.AttributesCu=1; assert(!aura.CanBeSaved()); spell.AttributesCu=0;
    aura.usesCharges=true; aura.charges=0; assert(!aura.CanBeSaved());
    aura.charges=1; assert(aura.CanBeSaved());
}
'''
with tempfile.TemporaryDirectory(prefix="loa-shaman-native-") as directory:
    for name, source in (("shaman", mocks + native + binding_mocks + tests),
                         ("aura", aura_mocks + aura_save + aura_tests)):
        cpp = pathlib.Path(directory) / (name + ".cpp")
        binary = pathlib.Path(directory) / name
        cpp.write_text(source)
        subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        str(cpp), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
print("Native shaman triggers, weapon targets and aura-save effects passed")
