// Opt-in native integration fixture. No creature spawns are saved to the DB.
#include "HunterStingTest.h"

#include "Action.h"
#include "AiObjectContext.h"
#include "AttackersValue.h"
#include "CharacterCache.h"
#include "Chat.h"
#include "Config.h"
#include "Map.h"
#include "MapManager.h"
#include "Pet.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "TemporarySummon.h"
#include "ThreatManager.h"
#include "Trigger.h"

#include <algorithm>
#include <array>

namespace
{
constexpr char ActionName[] = "serpent sting on attacker";
constexpr uint32 StingAura = 118253;
constexpr uint32 FreezeAura = 3355;
constexpr uint32 RootAura = 122;

class HunterStingTest : public WorldScript
{
public:
    HunterStingTest() : WorldScript("playerbot_hunter_sting_test") { }

    bool Start(ObjectGuid guid, bool rotation = false)
    {
        if (_guid)
            return false;
        _guid = guid;
        _elapsed = 0;
        _phase = 0;
        _next = 0;
        _setup = false;
        _targets = {};
        _rotation = rotation;
        _sawPrimary = _sawSecondary = _sawMark = _sawDamage = _sawBlackArrow = false;
        if (!sRandomPlayerbotMgr->GetPlayerBot(guid))
            sRandomPlayerbotMgr->AddPlayerBot(guid, 0);
        TC_LOG_INFO("playerbots", "Sting fixture started guid={} rotation={}", guid.GetCounter(), rotation);
        return true;
    }

    void Finish(bool passed, char const* reason)
    {
        if (!_guid)
            return;
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(_guid);
        if (_setup)
        {
            // Resolve by GUID, never retain Unit pointers across world updates.
            if (Map* map = sMapMgr->FindMap(_map, _instance))
                for (ObjectGuid guid : _targets)
                    if (Creature* target = map->GetCreature(guid))
                    {
                        target->CombatStop(true);
                        target->DespawnOrUnsummon();
                    }
            if (bot)
            {
                if (PlayerbotAI* ai = sPlayerbotsMgr->GetPlayerbotAI(bot))
                {
                    Unit* previous = _oldTarget ? ai->GetUnit(_oldTarget) : nullptr;
                    ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Set(previous);
                    ai->GetAiObjectContext()->GetValue<GuidVector>("attackers")->Reset();
                    ai->SetNextCheckDelay(0);
                }
                bot->SetSelection(_oldSelection);
                if (Pet* pet = bot->GetPet(); pet && pet->GetGUID() == _pet)
                    pet->SetReactState(_petReact);
            }
        }
        TC_LOG_INFO("playerbots", "Sting fixture finished guid={} passed={} phase={} reason={} cleanup=done combat={}",
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
        if (_elapsed > (_rotation ? 240000u : 90000u))
        {
            Finish(false, "timeout");
            return;
        }
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(_guid);
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || !bot->IsInWorld() || bot->IsBeingTeleported())
        {
            if (_setup)
                Finish(false, "bot unavailable");
            return;
        }
        if (!_setup)
        {
            if (ai->IsRealPlayer() || bot->GetClass() != CLASS_HUNTER || !bot->HasSpell(1978) ||
                !bot->IsAlive() || bot->IsInCombat() || bot->GetGroup() || bot->InBattleground() ||
                bot->IsMounted() || bot->IsInFlight() || bot->IsNonMeleeSpellCasted(true))
            {
                Finish(false, "preconditions");
                return;
            }
            _setup = true;
            _requiresBlackArrow = bot->HasSpell(3674);
            _map = bot->GetMapId();
            _instance = bot->GetInstanceId();
            _oldSelection = bot->GetTarget();
            Unit* oldTarget = ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
            _oldTarget = oldTarget ? oldTarget->GetGUID() : ObjectGuid::Empty;
            _pet.Clear();
            if (Pet* pet = bot->GetPet())
            {
                _pet = pet->GetGUID();
                _petReact = pet->GetReactState();
                if (!_rotation)
                    pet->SetReactState(REACT_PASSIVE);
            }
            bot->StopMoving();
            for (size_t i = 0; i < _targets.size(); ++i)
            {
                Position pos;
                bot->GetNearPoint(nullptr, pos.m_positionX, pos.m_positionY, pos.m_positionZ,
                    12.0f, bot->GetOrientation() + (float(i) - 1.0f) * 0.35f);
                TempSummon* target = bot->GetMap()->SummonCreature(30, pos, nullptr, _rotation ? 300s : 120s);
                if (!target)
                {
                    Finish(false, "summon failed");
                    return;
                }
                _targets[i] = target->GetGUID();
                target->SetTempSummonType(TEMPSUMMON_TIMED_DESPAWN);
                target->SetPhaseMask(bot->GetPhaseMask(), true);
                // Only these disposable fixture NPCs are inert and durable.
                // Threat discovery, target guards and spell effects stay native.
                target->IsAIEnabled = false;
                target->SetReactState(REACT_PASSIVE);
                target->SetFaction(14);
                target->SetMaxHealth((400000 - uint32(i) * 100000) * (_rotation ? 100 : 1));
                target->SetHealth(target->GetMaxHealth());
                target->GetThreatManager().AddThreat(bot, 1.0f);
            }
            ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Set(bot->GetMap()->GetCreature(_targets[0]));
            _rotationStarted = _elapsed;
            _next = _elapsed + 2000;
        }
        // CastSpell may set its own delay. Maintain isolation only for this
        // bounded fixture; world spell events and natural regeneration continue.
        if (!_rotation)
            ai->SetNextCheckDelay(90000);
        if (_elapsed < _next)
            return;
        if (!bot->IsAlive() || bot->GetMapId() != _map || bot->GetInstanceId() != _instance)
        {
            Finish(false, "bot changed world state");
            return;
        }
        std::array<Creature*, 3> targets;
        for (size_t i = 0; i < targets.size(); ++i)
        {
            targets[i] = bot->GetMap()->GetCreature(_targets[i]);
            if (!targets[i] || !targets[i]->IsAlive())
            {
                Finish(false, "target unavailable");
                return;
            }
        }
        auto* context = ai->GetAiObjectContext();
        if (_rotation)
        {
            // Observe the ordinary Engine. Do not call Trigger/Action, change
            // its strategies, inject auras or repeatedly set its chosen target.
            Unit* current = context->GetValue<Unit*>("current target")->Get();
            for (Creature* target : targets)
            {
                bool const sting = target->HasAura(StingAura, _guid);
                _sawPrimary |= sting && target == current;
                _sawSecondary |= sting && target != current;
                _sawMark |= target->HasAura(1130);
                _sawBlackArrow |= target->HasAura(3674, _guid);
                _sawDamage |= target->GetHealth() < target->GetMaxHealth();
                TC_LOG_INFO("playerbots", "Sting rotation guid={} elapsed_ms={} target={} current={} hp={} max_hp={} sting={} mark={} black_arrow={} focus={} spec={} known_black_arrow={}",
                    _guid.GetCounter(), _elapsed - _rotationStarted, target->GetGUID().GetCounter(),
                    target == current, target->GetHealth(), target->GetMaxHealth(), sting,
                    target->HasAura(1130), target->HasAura(3674, _guid), bot->GetPower(POWER_FOCUS),
                    bot->GetTalentSpecialization(), bot->HasSpell(3674));
            }
            if (_elapsed - _rotationStarted >= 120000)
            {
                TC_LOG_INFO("playerbots", "Sting rotation summary guid={} primary={} secondary={} mark={} damage={} black_arrow={} requires_black_arrow={} known_serpent_spread={}",
                    _guid.GetCounter(), _sawPrimary, _sawSecondary, _sawMark, _sawDamage, _sawBlackArrow,
                    _requiresBlackArrow, bot->HasSpell(87935));
                Finish(_sawPrimary && _sawSecondary && _sawMark && _sawDamage && (!_requiresBlackArrow || _sawBlackArrow),
                    "native Engine rotation observation");
                return;
            }
            _next = _elapsed + 1000;
            return;
        }
        // Combat began after login: refresh the normal activity predicate,
        // whose cached pre-combat result can otherwise last five seconds.
        bool const cachedActivity = ai->AllowActivity(ALL_ACTIVITY);
        bool const activity = ai->AllowActivity(ALL_ACTIVITY, true);
        auto* attackers = context->GetValue<GuidVector>("attackers");
        attackers->Reset();
        GuidVector found = attackers->Get();
        bool const discovered = std::all_of(_targets.begin(), _targets.end(), [&found](ObjectGuid guid)
            { return std::find(found.begin(), found.end(), guid) != found.end(); });
        if (_phase == 0)
            TC_LOG_INFO("playerbots", "Sting fixture activity guid={} cached={} refreshed={} combat={} threat_refs={} attackers={}",
                _guid.GetCounter(), cachedActivity, activity, bot->IsInCombat(),
                bot->GetThreatManager().GetThreatenedByMeList().size(), found.size());
        Trigger* trigger = context->GetTrigger(ActionName);
        Action* action = context->GetAction(ActionName);
        if (!discovered || found.size() != 3 || !trigger || !action)
        {
            TC_LOG_INFO("playerbots", "Sting fixture discovery guid={} count={} all={} trigger={} action={}",
                _guid.GetCounter(), found.size(), discovered, trigger != nullptr, action != nullptr);
            for (Creature* target : targets)
                TC_LOG_INFO("playerbots", "Sting fixture candidate guid={} target={} threat={} valid={} los={} attackable={}",
                    _guid.GetCounter(), target->GetGUID().GetCounter(), target->GetThreatManager().GetThreat(bot),
                    AttackersValue::IsValidTarget(target, bot), bot->IsWithinLOSInMap(target), bot->IsValidAttackTarget(target));
            Finish(false, "native attackers or factory");
            return;
        }
        auto check = [this](bool valid, char const* reason)
        {
            if (!valid)
                Finish(false, reason);
            return valid;
        };
        auto hasSting = [bot](Unit* unit) { return unit->HasAura(StingAura, bot->GetGUID()); };
        switch (_phase)
        {
            case 0:
            {
                if (!check(trigger->GetTarget() == targets[1] && trigger->IsActive() &&
                    action->GetTarget() == targets[1] && action->isUseful() && action->isPossible(), "initial eligibility"))
                    return;
                // Introduce real CC after validation, before Execute. AddAura
                // is test setup, not a claim that the Hunter cast Freezing Trap.
                if (!check(bot->AddAura(FreezeAura, targets[1]) != nullptr &&
                    targets[1]->HasBreakableByDamageCrowdControlAura(), "freeze setup"))
                    return;
                if (!check(trigger->GetTarget() == targets[2] && trigger->IsActive(), "trigger retarget"))
                    return;
                uint32 focus = bot->GetPower(POWER_FOCUS);
                _health = targets[2]->GetHealth();
                if (!check(action->Execute(Event()), "retarget cast rejected"))
                    return;
                TC_LOG_INFO("playerbots", "Sting fixture retarget guid={} attackers={} primary={} frozen={} selected={} focus_before={} focus_after={}",
                    _guid.GetCounter(), found.size(), _targets[0].GetCounter(), _targets[1].GetCounter(),
                    _targets[2].GetCounter(), focus, bot->GetPower(POWER_FOCUS));
                _next = _elapsed + 6000;
                break;
            }
            case 1:
            {
                if (!check(!hasSting(targets[0]) && !hasSting(targets[1]) && hasSting(targets[2]) &&
                    targets[1]->HasAura(FreezeAura, _guid) && targets[2]->GetHealth() < _health,
                    "retarget effect or CC preservation"))
                    return;
                uint32 focus = bot->GetPower(POWER_FOCUS);
                if (!check(!trigger->IsActive() && !action->GetTarget() && !action->Execute(Event()) &&
                    focus == bot->GetPower(POWER_FOCUS), "own sting repeat guard"))
                    return;
                TC_LOG_INFO("playerbots", "Sting fixture effect guid={} aura={} caster={} health_before={} health_after={} freeze_preserved=1 primary_clean=1 repeat_blocked=1",
                    _guid.GetCounter(), StingAura, _guid.GetCounter(), _health, targets[2]->GetHealth());
                targets[2]->RemoveAurasDueToSpell(StingAura, _guid);
                targets[1]->RemoveAurasDueToSpell(FreezeAura, _guid);
                if (!check(trigger->IsActive() && action->GetTarget() == targets[1] &&
                    action->isUseful() && action->isPossible(), "root prevalidation"))
                    return;
                for (size_t i : { 1u, 2u })
                    if (!check(bot->AddAura(RootAura, targets[i]) != nullptr &&
                        targets[i]->HasBreakableByDamageAuraType(SPELL_AURA_MOD_ROOT), "root setup"))
                        return;
                if (!check(!trigger->IsActive() && !action->GetTarget() && !action->Execute(Event()) &&
                    focus == bot->GetPower(POWER_FOCUS), "all controlled cast guard"))
                    return;
                _next = _elapsed + 2000;
                break;
            }
            case 2:
                if (!check(targets[1]->HasAura(RootAura, _guid) && targets[2]->HasAura(RootAura, _guid) &&
                    !hasSting(targets[1]) && !hasSting(targets[2]), "blocked cast effects"))
                    return;
                TC_LOG_INFO("playerbots", "Sting fixture blocked guid={} roots_preserved=2 sting_auras=0", _guid.GetCounter());
                targets[1]->RemoveAurasDueToSpell(RootAura, _guid);
                if (!check(trigger->GetTarget() == targets[1] && trigger->IsActive() &&
                    action->isUseful() && action->isPossible() && action->Execute(Event()), "recovery cast rejected"))
                    return;
                _next = _elapsed + 3000;
                break;
            case 3:
                if (!check(hasSting(targets[1]) && !hasSting(targets[0]) && !hasSting(targets[2]) &&
                    targets[2]->HasAura(RootAura, _guid), "recovery effect or root preservation"))
                    return;
                TC_LOG_INFO("playerbots", "Sting fixture recovery guid={} aura={} caster={} root_preserved=1 primary_clean=1",
                    _guid.GetCounter(), StingAura, _guid.GetCounter());
                Finish(true, "all checks passed");
                return;
        }
        ++_phase;
    }

private:
    ObjectGuid _guid, _oldTarget, _oldSelection, _pet;
    std::array<ObjectGuid, 3> _targets{};
    ReactStates _petReact = REACT_PASSIVE;
    uint32 _elapsed = 0, _next = 0, _phase = 0, _map = 0, _instance = 0, _health = 0;
    bool _setup = false;
    bool _rotation = false, _sawPrimary = false, _sawSecondary = false, _sawMark = false, _sawDamage = false;
    bool _sawBlackArrow = false, _requiresBlackArrow = false;
    uint32 _rotationStarted = 0;
};

HunterStingTest* Test = nullptr;
}

bool HandleHunterStingTest(ChatHandler* handler, std::string const& operation)
{
    int32 configured = sConfigMgr->GetIntDefault("AiPlayerbot.HunterStingTestGuid", 0);
    if (handler->GetSession() || configured <= 0 || !sPlayerbotAIConfig->enabled || !Test)
        return false;
    ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(uint32(configured));
    if (!sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid)))
        return false;
    if (operation == "start")
        return Test->Start(guid);
    if (operation == "rotation")
        return Test->Start(guid, true);
    if (operation == "cleanup")
    {
        Test->Finish(false, "console cleanup");
        return true;
    }
    handler->SendSysMessage("Usage: npcbot stingtest start/rotation/cleanup (opt-in native fixture; results in playerbots log)");
    return false;
}

void AddHunterStingTest() { Test = new HunterStingTest(); }
