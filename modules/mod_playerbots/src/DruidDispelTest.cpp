// Opt-in native fixture: existing spellbook, real Actions and dispel effects.
#include "DruidDispelTest.h"
#include "Action.h"
#include "AiObjectContext.h"
#include "CharacterCache.h"
#include "Chat.h"
#include "Config.h"
#include "DruidValues.h"
#include "Map.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "TemporarySummon.h"
#include "Trigger.h"

namespace
{
constexpr uint32 Poison = 2818, Curse = 1490, Magic = 122;
class DruidDispelTest : public WorldScript
{
public:
    DruidDispelTest() : WorldScript("playerbot_druid_dispel_test") {}
    bool Start(ObjectGuid guid)
    {
        if (_guid)
            return false;
        _guid = guid;
        _elapsed = _next = _phase = 0;
        _setup = false;
        _source.Clear();
        if (!sRandomPlayerbotMgr->GetPlayerBot(guid))
            sRandomPlayerbotMgr->AddPlayerBot(guid, 0);
        TC_LOG_INFO("playerbots", "Dispel fixture started guid={}", guid.GetCounter());
        return true;
    }
    void Finish(bool passed, char const* reason)
    {
        if (!_guid)
            return;
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(_guid);
        if (bot && _setup)
        {
            for (uint32 id : {Poison, Curse, Magic})
                bot->RemoveAurasDueToSpell(id, _source);
            if (_catApplied)
                bot->RemoveAurasDueToSpell(768, _guid);
            if (Creature* source = bot->GetMap()->GetCreature(_source))
            {
                source->CombatStop(true);
                source->DespawnOrUnsummon();
            }
            if (PlayerbotAI* ai = sPlayerbotsMgr->GetPlayerbotAI(bot))
                ai->SetNextCheckDelay(0);
        }
        TC_LOG_INFO("playerbots", "Dispel fixture finished guid={} passed={} phase={} reason={} cleanup=done combat={}",
            _guid.GetCounter(), passed, _phase, reason, bot && bot->IsInCombat());
        _guid.Clear();
    }
    void OnShutdownInitiate(ShutdownExitCode, ShutdownMask) override { Finish(false, "shutdown"); }
    void OnShutdown() override { Finish(false, "shutdown"); }
    void OnUpdate(uint32 diff) override
    {
        if (!_guid)
            return;
        _elapsed += diff;
        if (_elapsed > 120000)
        {
            Finish(false, "timeout");
            return;
        }
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(_guid);
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || !bot->IsInWorld() || bot->IsBeingTeleported())
            return;
        if (!_setup)
        {
            TC_LOG_INFO("playerbots", "Dispel fixture preconditions guid={} real={} class={} spell2782={} spell88423={} alive={} combat={} group={} bg={} mounted={} flight={} form={} casting={} poison={} curse={} magic={}",
                _guid.GetCounter(), ai->IsRealPlayer(), uint32(bot->GetClass()), bot->HasSpell(2782), bot->HasSpell(88423),
                bot->IsAlive(), bot->IsInCombat(), bot->GetGroup() != nullptr, bot->InBattleground(), bot->IsMounted(),
                bot->IsInFlight(), uint32(bot->GetShapeshiftForm()), bot->IsNonMeleeSpellCasted(true),
                bot->HasAura(Poison), bot->HasAura(Curse), bot->HasAura(Magic));
            if (ai->IsRealPlayer() || bot->GetClass() != CLASS_DRUID || !DruidDispelSpell(bot, DISPEL_POISON) ||
                !bot->IsAlive() || bot->IsInCombat() || bot->GetGroup() || bot->InBattleground() ||
                bot->IsMounted() || bot->IsInFlight() || bot->IsFlying() ||
                bot->IsNonMeleeSpellCasted(true) || bot->HasAura(Poison) || bot->HasAura(Curse) || bot->HasAura(Magic))
            {
                Finish(false, "preconditions");
                return;
            }
            // A previous BG can persist Cat/Bear Form. Normalize the fixture
            // with the existing cancellation Action, without granting spells
            // or bypassing the later native dispel's shapeshift check.
            if (bot->GetShapeshiftForm() != FORM_NONE)
            {
                Action* unshift = ai->GetAiObjectContext()->GetAction("caster form");
                if (!unshift || !unshift->Execute(Event()) || bot->GetShapeshiftForm() != FORM_NONE)
                {
                    Finish(false, "initial form cancellation");
                    return;
                }
            }
            Position pos;
            bot->GetNearPoint(nullptr, pos.m_positionX, pos.m_positionY, pos.m_positionZ, 4.0f, bot->GetOrientation());
            TempSummon* source = bot->GetMap()->SummonCreature(30, pos, nullptr, 150s);
            if (!source)
            {
                Finish(false, "summon failed");
                return;
            }
            source->SetTempSummonType(TEMPSUMMON_TIMED_DESPAWN);
            source->SetPhaseMask(bot->GetPhaseMask(), true);
            source->IsAIEnabled = false;
            source->SetReactState(REACT_PASSIVE);
            source->SetFaction(14);
            _source = source->GetGUID();
            _setup = true;
            _catApplied = false;
            bot->StopMoving();
            TC_LOG_INFO("playerbots", "Dispel fixture spellbook guid={} spec={} poison_spell={} magic_spell={}",
                _guid.GetCounter(), uint32(bot->GetTalentSpecialization()), DruidDispelSpell(bot, DISPEL_POISON),
                DruidDispelSpell(bot, DISPEL_MAGIC));
        }
        ai->SetNextCheckDelay(120000);
        if (_elapsed < _next)
            return;
        Creature* source = bot->GetMap()->GetCreature(_source);
        if (!source || !bot->IsAlive())
        {
            Finish(false, "fixture state changed");
            return;
        }
        auto* context = ai->GetAiObjectContext();
        auto check = [this](bool ok, char const* reason) { if (!ok) Finish(false, reason); return ok; };
        auto reset = [&] {
            for (uint32 type : {uint32(DISPEL_POISON), uint32(DISPEL_CURSE), uint32(DISPEL_MAGIC)})
                context->GetValue<Unit*>("party member to dispel", type)->Reset();
        };
        auto active = [&](char const* name) { Trigger* t = context->GetTrigger(name); return t && t->IsActive(); };
        auto inject = [&](uint32 id) { return source->AddAura(id, bot) != nullptr && bot->HasAura(id, _source); };
        Action* poison = context->GetAction("cure poison on party");
        Action* curse = context->GetAction("remove curse on party");
        Action* magic = context->GetAction("nature's cure on party");
        bool restoration = bot->GetTalentSpecialization() == SPEC_DRUID_RESTORATION;
        if (!check(poison && curse && magic, "factory registration"))
            return;
        switch (_phase)
        {
            case 0:
                reset();
                if (!check(!active("party member cure poison") && !poison->Execute(Event()), "clean target guard")) return;
                // Aura injection is scenario setup; the bot's dispel below is an ordinary Action cast.
                if (!check(inject(Poison) && inject(Curse) && inject(Magic), "aura setup")) return;
                reset();
                if (!check(active("party member cure poison") && active("party member remove curse") &&
                    active("party member cure magic") == restoration && poison->GetTarget() == bot &&
                    poison->isUseful() && poison->isPossible() && poison->Execute(Event()), "poison chain")) return;
                // Past the 1.5 s GCD, still inside the native 8 s dispel cooldown.
                _next = _elapsed + 2500;
                break;
            case 1:
                if (!check(!bot->HasAura(Poison) && !bot->HasAura(Curse) && bot->HasAura(Magic) == !restoration,
                    "native multi-type dispel effects")) return;
                TC_LOG_INFO("playerbots", "Dispel fixture effects guid={} poison=removed curse=removed magic_remaining={}",
                    _guid.GetCounter(), bot->HasAura(Magic));
                reset();
                if (!check(!poison->isUseful() && !poison->Execute(Event()), "empty repeat")) return;
                if (!check(inject(Poison), "cooldown setup")) return;
                reset();
                if (!check(!poison->isPossible() && !poison->Execute(Event()) && bot->HasAura(Poison), "native cooldown")) return;
                bot->RemoveAurasDueToSpell(Poison, _source);
                bot->RemoveAurasDueToSpell(Magic, _source);
                _next = _elapsed + 8500;
                break;
            case 2:
                if (!check(inject(Curse), "curse setup")) return;
                reset();
                if (!check(active("party member remove curse") && curse->isUseful() && curse->isPossible() &&
                    curse->Execute(Event()), "curse action")) return;
                _next = _elapsed + 2500;
                break;
            case 3:
                if (!check(!bot->HasAura(Curse), "curse effect")) return;
                _next = _elapsed + 8500;
                break;
            case 4:
                if (!check(inject(Magic), "magic setup")) return;
                reset();
                if (restoration)
                {
                    if (!check(active("party member cure magic") && magic->isUseful() && magic->isPossible() &&
                        magic->Execute(Event()), "Restoration magic action")) return;
                }
                else if (!check(!active("party member cure magic") && !magic->isUseful() &&
                    !magic->Execute(Event()) && bot->HasAura(Magic), "non-Restoration magic guard")) return;
                _next = _elapsed + 2500;
                break;
            case 5:
                if (!check(bot->HasAura(Magic) == !restoration, "magic effect")) return;
                bot->RemoveAurasDueToSpell(Magic, _source);
                if (!check(context->GetAction("cat form")->Execute(Event()), "native Cat Form")) return;
                _catApplied = true;
                _next = _elapsed + 8500;
                break;
            case 6:
            {
                if (!check(bot->GetShapeshiftForm() == FORM_CAT && inject(Curse), "shifted cure setup")) return;
                reset();
                NextAction** prerequisites = curse->getPrerequisites();
                bool caster = prerequisites && prerequisites[0]->getName() == "caster form";
                bool noPrerequisite = !prerequisites;
                NextAction::destroy(prerequisites);
                if (restoration)
                {
                    // Nature's Cure excludes Travel/Aquatic/flight, not Cat.
                    if (!check(noPrerequisite && curse->isPossible(), "Nature's Cure in Cat Form")) return;
                }
                else
                {
                    Action* unshift = context->GetAction("caster form");
                    if (!check(caster && unshift && unshift->isUseful() && unshift->isPossible() &&
                        unshift->Execute(Event()) && bot->GetShapeshiftForm() == FORM_NONE, "caster prerequisite")) return;
                }
                _next = _elapsed + 2000;
                break;
            }
            case 7:
                reset();
                if (!check(curse->isUseful() && curse->isPossible() && curse->Execute(Event()), "form-eligible cast")) return;
                _next = _elapsed + 2500;
                break;
            case 8:
                if (!check(!bot->HasAura(Curse) && bot->GetShapeshiftForm() == (restoration ? FORM_CAT : FORM_NONE),
                    "native dispel effect and form")) return;
                TC_LOG_INFO("playerbots", "Dispel fixture form effect guid={} form={} curse=removed", _guid.GetCounter(),
                    uint32(bot->GetShapeshiftForm()));
                Finish(true, "native effects, cooldown, repeat and specialization guards");
                return;
        }
        TC_LOG_INFO("playerbots", "Dispel fixture phase guid={} phase={} passed=1", _guid.GetCounter(), _phase);
        ++_phase;
    }
private:
    ObjectGuid _guid, _source;
    uint32 _elapsed = 0, _next = 0, _phase = 0;
    bool _setup = false, _catApplied = false;
};
DruidDispelTest* Test = nullptr;
}

bool HandleDruidDispelTest(ChatHandler* handler, std::string const& operation)
{
    int32 configured = sConfigMgr->GetIntDefault("AiPlayerbot.DruidDispelTestGuid", 0);
    if (handler->GetSession() || configured <= 0 || !sPlayerbotAIConfig->enabled || !Test)
        return false;
    ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(uint32(configured));
    if (!sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid)))
        return false;
    if (operation == "start")
        return Test->Start(guid);
    if (operation == "cleanup")
    {
        Test->Finish(false, "console cleanup");
        return true;
    }
    return false;
}
void AddDruidDispelTest() { Test = new DruidDispelTest(); }
