#!/usr/bin/env python3
"""Run real CastSpell/SpellEvent/EventProcessor bodies with bounded world doubles.

Spell::prepare is a double: source contracts pin event registration and result
reporting to the core. This is not a DBC/LOS integration test or a live BG test.
Optional --verify-mutations proves the old false-success/UAF failures are caught.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]


def method(text, signature):
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


ai = (root / "modules/mod_playerbots/src/AI/PlayerbotAI.cpp").read_text()
core = (root / "src/server/game/Spells/Spell.cpp").read_text()
header = (root / "src/server/game/Spells/Spell.h").read_text()
prepare = method(core, "void Spell::prepare(")
registration = "SpellEvent* Event = new SpellEvent(this);"
enqueue = "m_caster->m_Events.AddEvent(Event, m_caster->m_Events.CalculateTime(1));"
assert prepare.index(registration) < prepare.index(enqueue) < prepare.index("return;")
assert prepare.index(enqueue) < prepare.index("CheckCast(true)")
for error in ("SPELL_FAILED_SPELL_IN_PROGRESS", "SPELL_FAILED_SPELL_UNAVAILABLE"):
    assert f"SendCastResult({error});" in prepare
assert "m_castResult = result;" in prepare
assert "SpellCastResult m_castResult = SPELL_CAST_OK;" in header
check_range = method(core, "SpellCastResult Spell::CheckRange(")
assert "if (!strict && m_casttime == 0)" in check_range

unit_cast = method(ai, "bool PlayerbotAI::CastSpell(uint32 spellId, Unit*")
position_cast = method(ai, "bool PlayerbotAI::CastSpell(uint32 spellId, float")
named_cast = method(ai, "bool PlayerbotAI::CastSpell(std::string const name,")
actionbar_override = method(ai, "uint32 PlayerbotAI::GetActionbarOverride(")
send_result = method(core, "void Spell::SendCastResult(SpellCastResult result)")
event_class = header[header.index("class SpellEvent :"):header.index("class MissileData")]
events = "\n".join(method(core, signature) for signature in (
    "SpellEvent::SpellEvent(", "SpellEvent::~SpellEvent()",
    "bool SpellEvent::Execute(", "void SpellEvent::Abort(",
    "bool SpellEvent::IsDeletable() const"))

prefix = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <ctime>
#include <map>
#include <string>
#include <type_traits>
#include <vector>
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
using ObjectGuid = uint64;
#define TC_LOG_DEBUG(...) ((void)0)
#define TC_LOG_ERROR(...) assert(false && "non-deletable spell leaked")
enum SpellCastResult { SPELL_CAST_OK, SPELL_FAILED_OUT_OF_RANGE,
    SPELL_FAILED_LINE_OF_SIGHT, SPELL_FAILED_MOVING, SPELL_FAILED_NO_POWER,
    SPELL_FAILED_BAD_TARGETS, SPELL_FAILED_SPELL_IN_PROGRESS,
    SPELL_FAILED_SPELL_UNAVAILABLE };
enum { TRIGGERED_NONE, UNIT_STATE_IN_FLIGHT, UNIT_STAND_STATE_STAND,
    SPELL_EFFECT_OPEN_LOCK = 20, SPELL_EFFECT_SKINNING,
    TYPEID_PLAYER, TYPEID_UNIT, SMSG_CAST_FAILED,
    SPELL_AURA_OVERRIDE_ACTIONBAR_SPELLS,
    SPELL_AURA_OVERRIDE_ACTIONBAR_SPELLS_2 };
constexpr uint32 TARGET_FLAG_ITEM=1, TARGET_FLAG_DEST_LOCATION=2,
    TARGET_FLAG_SOURCE_LOCATION=4, SPELL_FACING_FLAG_INFRONT=1;
constexpr float CAST_ANGLE_IN_FRONT=1;
enum { SPELL_STATE_PREPARING, SPELL_STATE_FINISHED, SPELL_STATE_DELAYED };
struct Item {};
struct Effect { int Effect=0; };
struct SpellInfo {
    uint32 Id=42, Targets=0, FacingCasterFlags=0;
    ::Effect Effects[1];
    std::vector<uint32> OverrideSpellList;
};
struct SpellManager {
    SpellInfo info;
    std::map<uint32, SpellInfo> overrides;
    SpellInfo const* GetSpellInfo(uint32 id) {
        if (id == info.Id) return &info;
        auto itr = overrides.find(id);
        return itr == overrides.end() ? nullptr : &itr->second;
    }
} manager;
auto sSpellMgr = &manager;
struct Config { int reactDelay=100, globalCoolDown=1500; } config;
auto sPlayerbotAIConfig = &config;
struct MotionMaster {};
struct Session { bool loading=false; bool PlayerLoading() const { return loading; } };
struct Pet {
    bool known=false, toggled=false;
    std::vector<unsigned int> m_autospells;
    bool HasSpell(uint32) const { return known; }
    void ToggleAutocast(SpellInfo const*, bool) { toggled=true; }
};
struct AuraEffect {
    uint32 affectedSpell=0, amount=0;
    bool IsAffectingSpell(SpellInfo const* info) const {
        return info && info->Id == affectedSpell;
    }
    uint32 GetAmount() const { return amount; }
};
''' + without_includes((root / "src/common/Utilities/EventProcessor.h").read_text()) + r'''
struct WorldObject {};
struct Unit : WorldObject {
    using AuraEffectList = std::vector<AuraEffect const*>;
    ObjectGuid guid=7, selected=99;
    bool moving=false, flying=false, standing=true, trade=false, player=true;
    Pet* pet=nullptr;
    std::vector<uint32> knownSpells;
    AuraEffectList actionbarOverrides, secondaryActionbarOverrides;
    Session session;
    MotionMaster motion;
    EventProcessor m_Events;
    ObjectGuid GetGUID() const { return guid; }
    std::string GetName() const { return "test"; }
    Pet* GetPet() { return pet; }
    bool HasSpell(uint32 id) const {
        return std::find(knownSpells.begin(), knownSpells.end(), id) != knownSpells.end();
    }
    AuraEffectList const& GetAuraEffectsByType(int type) const {
        return type == SPELL_AURA_OVERRIDE_ACTIONBAR_SPELLS
            ? actionbarOverrides : secondaryActionbarOverrides;
    }
    bool IsFlying() const { return flying; }
    bool HasUnitState(int) const { return false; }
    bool IsStandState() const { return standing; }
    void SetStandState(int) { standing=true; }
    Unit* GetSelectedUnit() { return this; }
    void SetSelection(ObjectGuid value) { selected=value; }
    bool HasInArc(float, WorldObject*) { return true; }
    bool GetTradeData() { return trade; }
    bool isMoving() const { return moving; }
    MotionMaster* GetMotionMaster() { return &motion; }
    float GetAngle(float,float) { return 0; }
    void SetFacingTo(float) {}
    float GetPositionX() { return 1; }
    float GetPositionY() { return 2; }
    float GetPositionZ() { return 3; }
    int GetTypeId() const { return player ? TYPEID_PLAYER : TYPEID_UNIT; }
    Unit* ToPlayer() { return this; }
    Session* GetSession() { return &session; }
};
struct Facade { void SetFacingTo(Unit*, WorldObject*) {} } facade;
auto sServerFacade = &facade;
struct LastSpellCast {
    int writes=0;
    ObjectGuid target=0;
    void Set(uint32, ObjectGuid value, time_t) { ++writes; target=value; }
};
struct Position { int resets=0; void Reset() { ++resets; } };
using PositionMap = std::map<std::string,Position>;
template<class T> struct Value {
    std::remove_reference_t<T> value{};
    auto& Get() { return value; }
    void Set(std::remove_reference_t<T> v) { value=v; }
};
struct Context {
    Value<LastSpellCast&> last;
    Value<PositionMap&> positions;
    Value<time_t> timestamp;
    Value<uint32> spellId{42};
    template<class T> Value<T>* GetValue(std::string const&, std::string const& = "") {
        if constexpr (std::is_same_v<T,LastSpellCast&>) return &last;
        else if constexpr (std::is_same_v<T,PositionMap&>) return &positions;
        else if constexpr (std::is_same_v<T,time_t>) return &timestamp;
        else return &spellId;
    }
};
struct SpellCastTargets {
    void SetItemTarget(Item*) {}
    void SetUnitTarget(Unit*) {}
    void SetDst(Unit const&) {}
    void SetDst(float,float,float,float) {}
};
struct Spell;
''' + event_class + r'''
struct Spell {
    static inline int created=0, destroyed=0, cancelled=0, prepared=0, rechecks=0, packets=0;
    static inline uint32 lastInfo=0;
    static inline SpellCastResult outcome=SPELL_CAST_OK;
    static inline uint32 initialCastTime=0;
    static inline bool pending=false, deletable=true;
    Unit* m_caster;
    SpellInfo const* m_spellInfo;
    Item* m_CastItem=nullptr;
    int m_cast_count=0, m_customError=0, state=SPELL_STATE_PREPARING;
    SpellCastResult m_castResult=SPELL_CAST_OK;
    Spell(Unit* caster, SpellInfo const* info, int):m_caster(caster),m_spellInfo(info) {
        ++created; lastInfo=info->Id;
    }
    ~Spell() { ++destroyed; }
    uint32 GetCastTime() const { return initialCastTime; }
    void cancel() { ++cancelled; state=SPELL_STATE_FINISHED; }
    int getState() const { return state; }
    bool IsDeletable() const { return deletable; }
    Unit* GetCaster() { return m_caster; }
    void update(uint32) { if (!pending) state=SPELL_STATE_FINISHED; }
    uint64 GetDelayStart() { return 0; }
    uint64 handle_delayed(uint64) { return 0; }
    void SetDelayStart(uint64) {}
    uint64 GetDelayMoment() { return 1; }
    SpellCastResult CheckCast(bool strict) { ++rechecks; return strict ? outcome : SPELL_CAST_OK; }
    void SendCastResult(SpellCastResult result);
    static void SendCastResult(Unit*, SpellInfo const*, int, SpellCastResult, int, int) { ++packets; }
    void prepare(SpellCastTargets const*) {
        ++prepared;
''' + registration + "\n" + enqueue + r'''
        SendCastResult(outcome);
        if (outcome != SPELL_CAST_OK || !pending) state=SPELL_STATE_FINISHED;
    }
''' + method(header, "SpellCastResult GetCastResult() const") + r'''
};
struct PlayerbotAI {
    Unit* bot;
    Context context;
    Context* _aiObjectContext=&context;
    int delay=0;
    void SetNextCheckDelay(int value) { delay=value; }
    uint32 GetActionbarOverride(uint32) const;
    bool CastSpell(uint32, Unit*, Item* = nullptr);
    bool CastSpell(uint32, float, float, float, Item* = nullptr);
    bool CastSpell(std::string const, Unit*, Item* = nullptr);
};
''' + without_includes((root / "src/common/Utilities/EventProcessor.cpp").read_text()) + events

tests = r'''
void reset()
{
    assert(Spell::created == Spell::destroyed);
    Spell::created=Spell::destroyed=Spell::cancelled=Spell::prepared=Spell::rechecks=Spell::packets=0;
    Spell::lastInfo=0;
    Spell::outcome=SPELL_CAST_OK; Spell::initialCastTime=0;
    Spell::pending=false; Spell::deletable=true;
    manager.info=SpellInfo{}; manager.overrides.clear();
}
bool cast(PlayerbotAI& ai, Unit& target, int variant)
{
    if (variant == 0) return ai.CastSpell(42, &target);
    if (variant == 1) return ai.CastSpell(42, 1.f, 2.f, 3.f);
    return ai.CastSpell(std::string("test"), &target);
}
int main()
{
    // Each error is returned by prepare; a non-strict recheck would say OK.
    for (int variant : {0,1,2})
        for (SpellCastResult result : {SPELL_CAST_OK, SPELL_FAILED_OUT_OF_RANGE,
             SPELL_FAILED_LINE_OF_SIGHT, SPELL_FAILED_MOVING, SPELL_FAILED_NO_POWER,
             SPELL_FAILED_BAD_TARGETS, SPELL_FAILED_SPELL_IN_PROGRESS, SPELL_FAILED_SPELL_UNAVAILABLE})
            for (int audience : {0,1,2}) // normal player, loading player, NPC
            {
                reset();
                Unit bot, target; target.guid=88;
                bot.session.loading=audience == 1; bot.player=audience != 2;
                PlayerbotAI ai{&bot};
                ai.context.timestamp.value=123;
                ai.context.last.value.target=99;
                ai.context.positions.value["random"].resets=5;
                if (variant == 1) manager.info.Targets=TARGET_FLAG_DEST_LOCATION;
                Spell::outcome=result;
                assert(cast(ai,target,variant) == (result == SPELL_CAST_OK));
                assert(Spell::prepared == 1 && Spell::rechecks == 0);
                assert(Spell::destroyed == 0 && Spell::cancelled == 0);
                bool success=result == SPELL_CAST_OK;
                assert(ai.context.last.value.writes == int(success));
                assert(ai.context.last.value.target == (success ? (variant == 1 ? bot.guid : target.guid) : 99));
                assert(ai.context.positions.value["random"].resets == 5 + int(success));
                assert((ai.context.timestamp.value != 123) == (variant == 2 && success));
                assert(ai.delay == (variant == 1 && result == SPELL_FAILED_MOVING ? config.reactDelay : 0));
                assert(Spell::packets == int(!success && audience == 0));
                bot.m_Events.Update(1);
                assert(Spell::destroyed == 1 && Spell::cancelled == 0);
                bot.m_Events.KillAllEvents(true);
                assert(Spell::destroyed == 1);
            }
    for (int variant : {0,1})
    {
        // Pending successful casts remain event-owned through update and abort.
        reset();
        {
            Unit bot, target;
            PlayerbotAI ai{&bot};
            if (variant == 1) manager.info.Targets=TARGET_FLAG_SOURCE_LOCATION;
            Spell::pending=true;
            assert(cast(ai,target,variant));
            bot.m_Events.Update(1);
            assert(Spell::destroyed == 0);
            bot.m_Events.KillAllEvents(true);
            assert(Spell::cancelled == 1 && Spell::destroyed == 1);
        }
        // Finished but referenced spells must be rescheduled, not deleted.
        reset();
        {
            Unit bot, target;
            PlayerbotAI ai{&bot};
            if (variant == 1) manager.info.Targets=TARGET_FLAG_DEST_LOCATION;
            Spell::deletable=false;
            assert(cast(ai,target,variant));
            bot.m_Events.Update(1);
            assert(Spell::destroyed == 0);
            Spell::deletable=true;
            bot.m_Events.Update(1);
            assert(Spell::destroyed == 1);
        }
        // Logout/processor destruction cleans both pending and rejected spells.
        for (bool failure : {false,true})
        {
            reset();
            {
                Unit bot, target;
                PlayerbotAI ai{&bot};
                if (variant == 1) manager.info.Targets=TARGET_FLAG_DEST_LOCATION;
                Spell::pending=true;
                if (failure) Spell::outcome=SPELL_FAILED_BAD_TARGETS;
                assert(cast(ai,target,variant) == !failure);
                assert(Spell::destroyed == 0);
            }
            assert(Spell::destroyed == 1 && Spell::cancelled == int(!failure));
        }
    }
    // Before prepare no event owns the spell: caller must delete on rejection.
    for (int scenario : {0,1,2,3})
    {
        reset();
        Unit bot, target;
        PlayerbotAI ai{&bot};
        bool result;
        if (scenario == 0) {
            bot.moving=true; Spell::initialCastTime=1000;
            result=ai.CastSpell(42,&target);
            assert(ai.delay == config.reactDelay && Spell::cancelled == 1);
        } else if (scenario == 1) {
            result=ai.CastSpell(42,1.f,2.f,3.f); // No destination/source target.
        } else if (scenario == 2) {
            manager.info.Targets=TARGET_FLAG_DEST_LOCATION;
            manager.info.Effects[0].Effect=SPELL_EFFECT_OPEN_LOCK;
            result=ai.CastSpell(42,1.f,2.f,3.f);
        } else {
            manager.info.Targets=TARGET_FLAG_ITEM; bot.trade=true;
            result=ai.CastSpell(42,&target);
        }
        assert(result == (scenario == 3)); // Preserve existing trade special case.
        assert(Spell::prepared == 0 && Spell::created == 1 && Spell::destroyed == 1);
        bot.m_Events.Update(1);
        assert(Spell::destroyed == 1);
    }
    // Execute the production action-bar resolution used by unit casts.
    reset();
    {
        Unit bot, target;
        PlayerbotAI ai{&bot};
        manager.info.OverrideSpellList={84};
        manager.overrides[84].Id=84;
        bot.knownSpells={84};
        assert(ai.CastSpell(42,&target));
        assert(Spell::lastInfo == 84);
        bot.m_Events.Update(1);
        assert(Spell::destroyed == 1);
    }
    reset();
    {
        Unit bot, target;
        PlayerbotAI ai{&bot};
        manager.overrides[126].Id=126;
        AuraEffect overrideAura{42,126};
        bot.secondaryActionbarOverrides={&overrideAura};
        assert(ai.CastSpell(42,&target));
        assert(Spell::lastInfo == 126);
        bot.m_Events.Update(1);
        assert(Spell::destroyed == 1);
    }
    reset();
    {
        Unit bot, target;
        PlayerbotAI ai{&bot};
        Pet pet; pet.known=true; pet.m_autospells={42}; bot.pet=&pet;
        manager.info.OverrideSpellList={84};
        manager.overrides[84].Id=84;
        bot.knownSpells={84};
        assert(ai.CastSpell(42,&target));
        assert(pet.toggled && Spell::created == 0 && Spell::lastInfo == 0);
    }
    reset();
}
'''

environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                   UBSAN_OPTIONS="halt_on_error=1")
with tempfile.TemporaryDirectory(prefix="loa-playerbot-cast-") as directory:
    def run(label, unit, position, result_body, expected_failure=None):
        binary = Path(directory) / label
        source = prefix + result_body + actionbar_override + unit + position + named_cast + tests
        subprocess.run([compiler, "-x", "c++", "-std=c++20", "-g", "-O1",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-", "-o", str(binary)], input=source, text=True, check=True)
        result = subprocess.run([str(binary)], env=environment, capture_output=True, text=True)
        if expected_failure:
            assert result.returncode != 0 and expected_failure in result.stderr, result.stderr
            print(f"Mutation {label}: rejected ({expected_failure})")
        elif result.returncode:
            sys.stderr.write(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, [str(binary)])

    run("current", unit_cast, position_cast, send_result)
    if "--verify-mutations" in sys.argv[3:]:
        for label, unit, position in (
            ("unit-recheck", unit_cast.replace("spell->GetCastResult()", "spell->CheckCast(false)"), position_cast),
            ("position-recheck", unit_cast, position_cast.replace("spell->GetCastResult()", "spell->CheckCast(false)"))):
            run(label, unit, position, send_result, "Assertion")
        run("lost-early-result", unit_cast, position_cast,
            send_result.replace("m_castResult = result;", ""), "Assertion")
        for label, unit, position in (
            ("unit-delete", unit_cast.replace("if (result != SPELL_CAST_OK)\n    {",
                 "if (result != SPELL_CAST_OK)\n    {\n        delete spell;"), position_cast),
            ("position-delete", unit_cast, position_cast.replace("if (result != SPELL_CAST_OK)\n    {",
                 "if (result != SPELL_CAST_OK)\n    {\n        delete spell;"))):
            # Skip the early destruction counter to let the real queued event
            # expose the dangling pointer under ASan.
            original_tests = tests
            tests = tests.replace("assert(Spell::destroyed == 0 && Spell::cancelled == 0);", "")
            run(label, unit, position, send_result, "heap-use-after-free")
            tests = original_tests
print("Playerbot cast result and SpellEvent ownership regressions: PASS")
