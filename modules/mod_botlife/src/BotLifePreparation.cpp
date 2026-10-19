#include "BotLifePreparation.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Log.h"
#include "Map.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include <cstring>
#include <list>

namespace BotLife
{
QuestPreparation::QuestPreparation(PlayerbotAI& ai, QuestSafety& safety)
    : _bot(*ai.GetBot()), _safety(safety), _movement(ai, [&safety] { return safety.RouteSafe(); }), _travel(_movement) { }

bool QuestPreparation::NeedsService() const
{
    return EvaluateReadiness(ReadCombatReadiness(_bot), _resting).state != Preparation::Ready;
}

void QuestPreparation::Report(Readiness const& s, char const* reason)
{
    if (std::strcmp(_reason, reason) == 0)
        return;
    _reason = reason;
    TC_LOG_INFO("playerbots.botlife", "BotLife preparation guid={} reason={} level={} equipped={} armor={} ilvl={} weapon={} offhand={} spells={} durability={} broken={} health={} mana={} usesMana={} sickness={}",
        _bot.GetGUID().GetCounter(), reason, s.level, s.equipped, s.armorPieces, s.averageItemLevel,
        s.weapon, s.offhand, s.combatSpell, s.durability, s.broken, s.health, s.mana, s.usesMana, s.resurrectionSickness);
}

PreparationResult QuestPreparation::Update(uint32_t elapsed)
{
    Readiness const s = ReadCombatReadiness(_bot);
    PreparationDecision const decision = EvaluateReadiness(s, _resting);
    if (decision.state == Preparation::Unprepared)
    {
        Report(s, decision.reason);
        Pause();
        return PreparationResult::Failed;
    }
    if (decision.state == Preparation::Ready)
    {
        Report(s, decision.reason);
        Pause();
        _resting = false;
        return PreparationResult::Ready;
    }
    _holding = true;
    _waitMs += elapsed;
    if (_waitMs >= 600000)
    {
        Report(s, "preparation-timeout");
        Pause();
        return PreparationResult::Failed;
    }
    _safety.SetTarget(0); // No hostile may be pulled on a service detour.
    if (decision.state == Preparation::Rest || s.health < 90 || (s.usesMana && s.mana < 80) || s.resurrectionSickness)
        return Rest(s);
    _resting = false;
    Report(s, decision.reason);
    return Repair(elapsed);
}

PreparationResult QuestPreparation::Rest(Readiness const& s)
{
    _resting = true;
    _travel.Cancel();
    _vendor.reset();
    if (!_safety.CanRest())
    {
        if (_sitting && _bot.IsSitState())
            _bot.SetStandState(UNIT_STAND_STATE_STAND);
        _sitting = false;
        Report(s, "unsafe-rest-position");
        return PreparationResult::Waiting; // Do not sit down within an aggro perimeter.
    }
    Report(s, s.resurrectionSickness ? "resurrection-sickness" : s.health < 90 ? "low-health" : "low-mana");
    if (!_bot.IsInCombat() && !_bot.IsNonMeleeSpellCasted(false) && !_bot.IsMounted() &&
        _bot.GetMotionMaster()->GetCurrentMovementGeneratorType() == IDLE_MOTION_TYPE && _bot.movespline->Finalized())
    {
        if (!_bot.IsSitState())
        {
            _bot.SetStandState(UNIT_STAND_STATE_SIT);
            _sitting = true;
        }
    }
    // Native regeneration only. No SetHealth/SetPower, conjured items or free repair.
    return PreparationResult::Waiting;
}

PreparationResult QuestPreparation::Repair(uint32_t elapsed)
{
    if (_sitting && _bot.IsSitState())
        _bot.SetStandState(UNIT_STAND_STATE_STAND);
    _sitting = false;
    if (!_vendor)
    {
        auto check = [this](Creature* npc)
        {
            return npc->GetSpawnId() && npc->IsAlive() && !npc->IsInCombat() &&
                npc->HasFlag(UNIT_FIELD_NPC_FLAGS, UNIT_NPC_FLAG_REPAIR) && !_bot.IsHostileTo(npc) &&
                _bot.CanSeeOrDetect(npc) && _bot.IsWithinDistInMap(npc, 150);
        };
        std::list<Creature*> vendors;
        Trinity::CreatureListSearcher<decltype(check)> searcher(&_bot, vendors, check);
        Cell::VisitAllObjects(&_bot, searcher, 150);
        vendors.sort([this](Creature* a, Creature* b) { return _bot.GetDistance(a) < _bot.GetDistance(b); });
        for (Creature* npc : vendors)
        {
            QuestSpawn candidate{npc->GetSpawnId(), npc->GetEntry(), _bot.GetMapId(), npc->GetPhaseMask(),
                npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()};
            if (_safety.CanApproach(candidate))
            {
                _vendor = candidate;
                _travel.Start({_bot.GetMapId(), _bot.GetInstanceId(), _bot.GetPhaseMask(), candidate.x, candidate.y, candidate.z, 3.0f});
                break;
            }
        }
        if (!_vendor)
        {
            _reason = "no-safe-local-repair-npc";
            return PreparationResult::Failed;
        }
    }
    if (!_safety.CanApproach(*_vendor) || (_travel.ControlsMovement() && !_safety.RouteSafe()))
    {
        Pause();
        _reason = "unsafe-repair-route";
        return PreparationResult::Failed;
    }
    TravelStatus const status = _travel.Update(elapsed);
    if (status == TravelStatus::Failed || status == TravelStatus::Cancelled)
    {
        _reason = "repair-travel-failed";
        return PreparationResult::Failed;
    }
    if (status != TravelStatus::Arrived)
        return PreparationResult::Waiting;
    _travel.Cancel();
    Creature* npc = _bot.GetMap()->GetCreatureBySpawnId(_vendor->guid);
    if (!npc || npc->GetEntry() != _vendor->entry || npc->IsInCombat() ||
        !_bot.GetNPCIfCanInteractWith(npc->GetGUID(), UNIT_NPC_FLAG_REPAIR))
    {
        _reason = "repair-interaction-refused";
        return PreparationResult::Failed;
    }
    uint64 const moneyBefore = _bot.GetMoney();
    _bot.DurabilityRepairAll(true, _bot.GetReputationPriceDiscount(npc), false);
    uint64 const spent = moneyBefore - _bot.GetMoney(); // Native return value counts guild withdrawals only.
    Readiness const after = ReadCombatReadiness(_bot);
    TC_LOG_INFO("playerbots.botlife", "BotLife preparation guid={} event=repair npc={} spent={} durability={} broken={}",
        _bot.GetGUID().GetCounter(), _vendor->guid, spent, after.durability, after.broken);
    _vendor.reset();
    // Native repair may be partial when money is insufficient. Never retry
    // indefinitely, borrow from guild funds or claim success from a paid sum.
    if (after.broken || after.durability < 100)
    {
        _reason = "repair-incomplete-or-unaffordable";
        return PreparationResult::Failed;
    }
    return PreparationResult::Waiting; // Recheck all readiness gates next tick.
}

void QuestPreparation::Pause()
{
    _travel.Cancel();
    _vendor.reset();
    if (_sitting && _bot.IsSitState())
        _bot.SetStandState(UNIT_STAND_STATE_STAND);
    _sitting = _holding = false;
}
}
