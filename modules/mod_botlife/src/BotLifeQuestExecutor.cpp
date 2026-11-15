#include "BotLifeQuestExecutor.h"
#include "BotLifeMovement.h"
#include "BotLifeQuestData.h"
#include "BotLifeQuestHunt.h"
#include "BotLifeQuestInteraction.h"
#include "BotLifeQuestTurnIn.h"
#include "BotLifePreparation.h"
#include "BotLifeProvisioning.h"
#include "BotLifeRouteClearance.h"
#include "BotLifeAbilities.h"

#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "Timer.h"
#include <algorithm>
#include <cstring>

namespace BotLife
{
namespace
{
class QuestExecutor final : public ActivityExecutor
{
public:
    QuestExecutor(PlayerbotAI& ai, QuestPlanData const& data)
        : _data(data), _hunt(ai), _movement(ai, [this] { return _hunt.Safety().RouteSafe(); }),
          _travel(_movement), _preparation(ai, _hunt.Safety()), _clearance(ai, _hunt) { }
    ActivityType GetType() const override { return ActivityType::Quest; }
    void Start(PlayerbotAI& ai) override
    {
        Player& bot = *ai.GetBot();
        _guid = bot.GetGUID().GetCounter();
        _context = {bot.GetMapId(), bot.GetInstanceId(), bot.GetPhaseMask(),
            bot.GetPositionX(), bot.GetPositionY(), bot.GetPositionZ(), 1.0f};
        _wallStartedAt = _startedAt = _progressAt = getMSTime();
        _result = ActivityResult::Running;
        QuestPlayerSnapshot const player = ReadQuestPlayer(_data, bot);
        _hadQuest = player.progress != QuestProgress::NotTaken;
        _counters = player.counters;
        if (player.progress == QuestProgress::Rewarded)
            Fail("already-rewarded");
        if (_result == ActivityResult::Running)
        {
            if (char const* reason = QuestExecutionRejection(bot, _data))
                Fail(reason);
            else if (!_movement.IsValid(_context))
                Fail("invalid-context");
            else if (!ProvisionMissingEquipment(ai, _reason))
                Fail(_reason);
        }
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=start resumed={} result={}",
            _guid, _data.questId, _hadQuest, ToString(_result));
        if (_result == ActivityResult::Running)
            LogEnhancementAbilities(ai); // One diagnostic snapshot, never on the update hot path.
    }
    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        if (_result != ActivityResult::Running)
            return _result;
        if (_recovering)
            return IsDeathRecoveryExpired() ? Fail("death-recovery-timeout") : ActivityResult::Running;
        Player& bot = *ai.GetBot();
        if (!IsEligibleBot(_guid) || !_movement.IsValid(_context))
            return Fail("invalid-context");
        if (char const* reason = QuestExecutionRejection(bot, _data))
            return Fail(reason);
        if (GetMSTimeDiffToNow(_startedAt) >= 20 * 60 * 1000 || GetMSTimeDiffToNow(_wallStartedAt) >= 30 * 60 * 1000)
            return Fail("quest-timeout");
        QuestPlayerSnapshot const player = ReadQuestPlayer(_data, bot);
        if (!_routeObserved || (player.x - _routeX) * (player.x - _routeX) +
            (player.y - _routeY) * (player.y - _routeY) + (player.z - _routeZ) * (player.z - _routeZ) >= 9)
        {
            _routeObserved = true;
            _routeX = player.x; _routeY = player.y; _routeZ = player.z;
            _routeProgressAt = getMSTime();
        }
        if (_hadQuest && player.progress == QuestProgress::NotTaken)
            return Fail("quest-removed"); // Never reaccept or reset a lost quest.
        for (QuestKillObjective const& objective : _data.objectives)
        {
            auto const current = player.counters.find(objective.id);
            uint32 const value = current == player.counters.end() ? 0 : current->second;
            if (value > _counters[objective.id])
            {
                _progressAt = getMSTime();
                TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=progress objective={} count={} required={}",
                    _guid, _data.questId, objective.id, value, objective.amount);
            }
        }
        _counters = player.counters;
        QuestPlan const plan = BuildQuestPlan(_data, player);
        if (plan.stage == QuestPlanStage::Rejected)
            return Fail(ToString(plan.reason));
        if (plan.stage == QuestPlanStage::Done)
            return Fail("rewarded-externally"); // Our own native reward finishes in the interaction below.
        if (plan.stage != _stage)
        {
            ClearTarget();
            _stage = plan.stage;
            _routeProgressAt = getMSTime();
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=stage stage={}",
                _guid, _data.questId, ToString(_stage));
        }
        if (_stage == QuestPlanStage::AwaitCompletion)
        {
            // Native kill processing must mark Complete. Never manufacture completion.
            if (GetMSTimeDiffToNow(_progressAt) >= 180000)
                return Fail("native-completion-timeout");
            return ActivityResult::Running;
        }
        if (_clearance.Active())
        {
            ClearanceResult const result = _clearance.Update(elapsed);
            if (result == ClearanceResult::Failed)
                DeferTarget();
            if (result != ClearanceResult::Running)
                _preparation.RequireRecovery();
            return ActivityResult::Running; // Next tick rechecks readiness before resuming the preserved route.
        }
        if (!_engaged && !_hunt.IsFighting())
        {
            if (_preparation.NeedsService())
            {
                _travel.Cancel();
                _travelling = false; // Keep the destination while recovering between sequential fights.
                _detouring = false; // Replan from the post-service position.
            }
            PreparationResult const preparation = _preparation.Update(elapsed);
            if (preparation == PreparationResult::Failed)
                return Fail(_preparation.Reason());
            if (preparation == PreparationResult::Waiting)
            {
                _startedAt += elapsed;
                _progressAt += elapsed; // Service time is bounded separately; no synthetic credit.
                _routeProgressAt = getMSTime(); // Service movement may already have renewed this clock.
                return ActivityResult::Running;
            }
        }
        bool const wasWaitingSafety = _waitingSafety;
        if (!_engaged && !_hunt.IsFighting() && GetMSTimeDiffToNow(_routeProgressAt) >= 180000)
            return Fail("quest-route-no-progress"); // Bound an actually stalled route, including Hunt.
        if (_safetyCooldown && GetMSTimeDiffToNow(_safetyAt) < _safetyDelay)
            return ActivityResult::Running;
        _safetyCooldown = false;
        _waitingSafety = false;
        if (_detouring)
        {
            _hunt.Safety().SetTarget(0);
            if (!_hunt.Safety().CanApproach(_detourPoint) ||
                (_travel.ControlsMovement() && !_hunt.Safety().RouteSafe()))
            {
                DeferTarget();
                return ActivityResult::Running;
            }
            TravelStatus const detour = _travel.Update(elapsed);
            if (detour == TravelStatus::Arrived)
            {
                _travel.Cancel();
                _detouring = _travelling = false; // Retain the real quest target.
                TC_LOG_INFO("playerbots.botlife", "BotLife detour guid={} event=waypoint-reached", _guid);
            }
            else if (detour == TravelStatus::Failed || detour == TravelStatus::Cancelled)
                DeferTarget();
            return ActivityResult::Running; // No quest credit/timer reset for a waypoint.
        }
        if (_stage == QuestPlanStage::Hunt)
        {
            if (_engaged)
            {
                if (GetMSTimeDiffToNow(_engagedAt) >= 30000 && _hunt.CancelUnstartedAttack(*_target))
                    RetireTarget();
                else if (!_hunt.IsAlive(*_target))
                    RetireTarget();
                else if (GetMSTimeDiffToNow(_engagedAt) >= 30000 && !_hunt.IsFighting())
                    RetireTarget();
                return ActivityResult::Running; // Combat engine owns the target, even before combat flag.
            }
            if (_hunt.IsFighting())
                return ActivityResult::Running;
            if (bot.IsMounted())
            {
                ClearTarget();
                return ActivityResult::Running;
            }
            if (!_target)
            {
                if (_visits >= 128)
                    return Fail("target-limit");
                // A patrol veto is temporary. Recheck only after a cooldown,
                // without forgetting permanent visits or resetting run budgets.
                auto excluded = _visited;
                for (auto it = _deferred.begin(); it != _deferred.end();)
                    if (GetMSTimeDiffToNow(it->second) >= 45000)
                        it = _deferred.erase(it);
                    else
                    {
                        excluded.insert(it->first);
                        ++it;
                    }
                std::optional<QuestSpawn> obstructed;
                uint32 blocker = 0;
                _target = _hunt.Choose(_data, player, excluded, &obstructed, &blocker);
                if (!_target && obstructed)
                {
                    _target = obstructed;
                    if (TryDetour() || TryClearRoute(blocker))
                        return ActivityResult::Running;
                    _target.reset();
                }
                if (!_target)
                {
                    if (!wasWaitingSafety)
                        TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=wait reason=no-safe-quest-target",
                            _guid, _data.questId);
                    WaitForSafety();
                    return ActivityResult::Running;
                }
            }
            if (_hunt.CanEngage(*_target))
            {
                _travel.Cancel();
                _travelling = false;
                if (_hunt.Engage(*_target))
                {
                    CountVisit();
                    _engaged = true;
                    _engagedAt = getMSTime();
                    TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=engage spawn={} entry={}",
                        _guid, _data.questId, _target->guid, _target->entry);
                }
                else
                    RetireTarget();
                return ActivityResult::Running;
            }
        }
        else if (!_target)
            _target = _stage == QuestPlanStage::Acquire ? plan.starter : plan.ender;

        if (!_target)
            return Fail("missing-target");
        _hunt.Safety().SetTarget(_stage == QuestPlanStage::Hunt ? _target->guid : 0);
        if (!_hunt.Safety().CanApproach(*_target) || (_travel.ControlsMovement() && !_hunt.Safety().RouteSafe()))
        {
            if (std::strcmp(_hunt.Safety().Reason(), "hostile-on-route") == 0)
            {
                uint32 const blocker = _hunt.Safety().Blocker();
                if (TryDetour() || TryClearRoute(blocker))
                    return ActivityResult::Running;
            }
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=unsafe-route spawn={}",
                _guid, _data.questId, _target->guid);
            if (_stage == QuestPlanStage::Hunt)
                DeferTarget();
            else
            {
                ClearTarget();
                WaitForSafety();
            }
            return ActivityResult::Running;
        }
        if (!_travelling)
        {
            TravelTarget target = _context;
            target.x = _target->x; target.y = _target->y; target.z = _target->z;
            _travel.Start(target);
            _travelling = true;
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=travel stage={} spawn={} entry={}",
                _guid, _data.questId, ToString(_stage), _target->guid, _target->entry);
        }
        TravelStatus const travel = _travel.Update(elapsed);
        if (_stage == QuestPlanStage::Hunt && _travel.ControlsMovement())
            CountVisit(); // A rejected spline is not a visit; successful dispatch is.
        if (travel == TravelStatus::Failed || travel == TravelStatus::Cancelled)
        {
            if (_travel.GetFailure() == TravelFailure::UnsafeRoute &&
                std::strcmp(_hunt.Safety().Reason(), "hostile-on-route") == 0)
            {
                uint32 const blocker = _hunt.Safety().Blocker();
                if (TryDetour() || TryClearRoute(blocker))
                    return ActivityResult::Running;
            }
            if (_travel.GetFailure() == TravelFailure::UnsafeRoute)
            {
                TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=skip spawn={} reason={}",
                    _guid, _data.questId, _target->guid, ToString(_travel.GetFailure()));
                if (_stage == QuestPlanStage::Hunt)
                    DeferTarget();
                else
                {
                    // Acquire/TurnIn have one authoritative interaction target. Hunt-style
                    // retirement cannot select an alternative and otherwise hot-loops on it.
                    ClearTarget();
                    WaitForSafety();
                }
                return ActivityResult::Running;
            }
            if (_stage != QuestPlanStage::Hunt || _travel.GetFailure() == TravelFailure::MovementLost ||
                _travel.GetFailure() == TravelFailure::InvalidTarget || _travel.GetFailure() == TravelFailure::RecoveryExhausted)
                return Fail(ToString(_travel.GetFailure()));
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=skip spawn={} reason={}",
                _guid, _data.questId, _target->guid, ToString(_travel.GetFailure()));
            RetireTarget();
        }
        else if (travel == TravelStatus::Arrived)
        {
            _travel.Cancel();
            _travelling = false;
            if (_stage == QuestPlanStage::Hunt)
            {
                CountVisit(); // Includes inspecting a spawn location already underfoot.
                RetireTarget(); // No live eligible target at the cached location; try another spawn.
            }
            else if (_stage == QuestPlanStage::Acquire)
            {
                if (!TryAcceptQuest(bot, _data, *_target, _reason))
                    return Fail(_reason);
                _hadQuest = true;
                _progressAt = getMSTime();
                ClearTarget();
            }
            else
            {
                // One invocation only. Failure is terminal, so hooks/rewards cannot be retried.
                if (!TryTurnInQuest(bot, _data, *_target, _reason))
                    return Fail(_reason);
                _rewarded = true;
                _result = ActivityResult::Completed;
                ClearTarget();
            }
        }
        return _result;
    }
    void Pause(PlayerbotAI&) override
    {
        _clearance.Pause();
        _preparation.Pause();
        if (_travelling)
            _travel.Pause();
    }
    bool Resume(PlayerbotAI& ai) override
    {
        if (_result != ActivityResult::Running || !IsEligibleBot(_guid) || !_movement.IsValid(_context) ||
            QuestExecutionRejection(*ai.GetBot(), _data))
            return false;
        if (_recovering)
        {
            if (IsDeathRecoveryExpired())
                return false;
            QuestPlayerSnapshot const player = ReadQuestPlayer(_data, *ai.GetBot());
            if ((_hadQuest && player.progress == QuestProgress::NotTaken) || player.progress == QuestProgress::Rewarded)
                return false;
            _startedAt += GetMSTimeDiffToNow(_deathAt); // Recovery is not quest work.
            _progressAt = getMSTime(); // Fresh bounded window, not synthetic quest credit.
            _routeProgressAt = getMSTime();
            _recovering = false;
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=resurrected deaths={}",
                _guid, _data.questId, _deaths);
            return true; // Re-read native status/counters and choose a fresh target on Update.
        }
        if (_engaged)
            RetireTarget();
        return !_travelling || _travel.Resume();
    }
    bool SuspendForDeath(PlayerbotAI&) override
    {
        if (_result != ActivityResult::Running)
            return false;
        if (!_recovering)
        {
            _recovering = true;
            _deathAt = getMSTime();
            ++_deaths;
            _preparation.Pause();
            _hunt.Safety().RememberDeath();
            DeferTarget(false); // Death memory owns retry policy; this is not a route failure.
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=death-wait deaths={}",
                _guid, _data.questId, _deaths);
        }
        return true;
    }
    bool IsDeathRecoveryExpired() const override
    {
        return _recovering && (GetMSTimeDiffToNow(_deathAt) >= 10 * 60 * 1000 ||
            GetMSTimeDiffToNow(_wallStartedAt) >= 30 * 60 * 1000);
    }
    void Interrupt(PlayerbotAI&, InterruptReason reason) override
    {
        Fail(ToString(reason));
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=cancel reason={}",
            _guid, _data.questId, _reason);
    }
    void Finish(PlayerbotAI&, ActivityResult result) override
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=finish result={} rewarded={} reason={} visits={} deaths={}",
            _guid, _data.questId, ToString(result), _rewarded, _reason, _visits, _deaths);
        ClearTarget();
        _preparation.Pause();
    }
    bool ControlsMovement() const override { return (_travelling && _travel.ControlsMovement()) || _preparation.ControlsMovement() || _clearance.ControlsMovement(); }
    bool HoldsNonCombat() const override
    {
        // A pending route may be waiting for an already running native
        // non-combat spline to finish. Do not cancel that spline, but prevent
        // base AI from continuously replacing it before BotLife can acquire
        // the now-idle movement slot.
        return _travelling || _waitingSafety || _preparation.HoldsNonCombat() || _clearance.HoldsNonCombat();
    }

private:
    void CountVisit()
    {
        if (!_visitCounted)
        {
            _visitCounted = true;
            if (_target && _countedVisits.insert(_target->guid).second)
                ++_visits; // One visit per spawn even after a temporary route retry.
        }
    }
    void WaitForSafety()
    {
        _waitingSafety = _safetyCooldown = true;
        _safetyAt = getMSTime();
        _safetyDelay = 5000;
        // Wake when the nearest deferred spawn becomes eligible, not one
        // full polling interval later. uint32 subtraction remains wrap-safe.
        for (auto const& entry : _deferred)
        {
            uint32 const age = GetMSTimeDiffToNow(entry.second);
            if (age < 45000)
                _safetyDelay = std::min(_safetyDelay, 45000u - age);
        }
    }
    bool TryClearRoute(uint32 blocker)
    {
        if (_clearance.Attempted(blocker))
        {
            TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=retire spawn={} reason=blocker-already-attempted blocker={}",
                _guid, _data.questId, _target ? _target->guid : 0, blocker);
            if (_stage == QuestPlanStage::Hunt)
                RetireTarget();
            else
            {
                ClearTarget();
                WaitForSafety();
            }
            return true;
        }
        if (!_clearance.Start(blocker))
            return false;
        _preparation.RequireRecovery();
        _travel.Cancel();
        _travelling = false;
        _waitingSafety = false;
        return true;
    }
    bool TryDetour()
    {
        if (!_target || _detourAttempts >= 8 || _hunt.IsFighting())
            return false;
        _hunt.Safety().SetTarget(_stage == QuestPlanStage::Hunt ? _target->guid : 0);
        auto point = _hunt.Safety().FindDetour(*_target);
        if (!point)
        {
            if (_hunt.Safety().DetourPending())
            {
                _travel.Cancel();
                _travelling = false;
                WaitForSafety(); // Preserve this target for the wider search, not clearance yet.
                return true;
            }
            return false;
        }
        _travel.Cancel();
        _detourPoint = *point;
        TravelTarget waypoint = _context;
        waypoint.x = point->x; waypoint.y = point->y; waypoint.z = point->z;
        _hunt.Safety().SetTarget(0);
        _travel.Start(waypoint);
        ++_detourAttempts;
        _detouring = _travelling = true;
        _waitingSafety = false;
        return true;
    }
    void ClearTarget()
    {
        _clearance.Cancel();
        _travel.Cancel();
        _travelling = _engaged = _visitCounted = _detouring = false;
        _target.reset();
        _hunt.Safety().SetTarget(0);
    }
    void RetireTarget()
    {
        if (_target)
        {
            _visited.insert(_target->guid);
            _deferred.erase(_target->guid);
            _routeFailures.erase(_target->guid);
        }
        ClearTarget();
    }
    void DeferTarget(bool routeFailure = true)
    {
        if (_target)
        {
            uint32 const spawn = _target->guid;
            if (routeFailure && ++_routeFailures[spawn] >= 2)
            {
                TC_LOG_INFO("playerbots.botlife", "BotLife quest-run guid={} quest={} event=retire spawn={} reason=repeated-unsafe-route failures={}",
                    _guid, _data.questId, spawn, _routeFailures[spawn]);
                _visited.insert(spawn);
                _deferred.erase(spawn);
                ClearTarget();
                return;
            }
            _deferred[spawn] = getMSTime();
        }
        ClearTarget();
        WaitForSafety();
    }
    ActivityResult Fail(char const* reason)
    {
        _reason = reason;
        ClearTarget();
        _preparation.Pause();
        return _result = ActivityResult::Failed;
    }
    QuestPlanData const& _data;
    QuestHunt _hunt;
    NativeTravelMovement _movement;
    TravelExecutor _travel;
    QuestPreparation _preparation;
    RouteClearance _clearance;
    TravelTarget _context;
    std::optional<QuestSpawn> _target;
    QuestSpawn _detourPoint{};
    uint32 _detourAttempts = 0;
    bool _detouring = false;
    std::unordered_set<uint32_t> _visited;
    std::unordered_set<uint32_t> _countedVisits;
    std::unordered_map<uint32_t, uint32_t> _deferred;
    std::unordered_map<uint32_t, uint32_t> _routeFailures;
    std::unordered_map<uint32_t, uint32_t> _counters;
    QuestPlanStage _stage = QuestPlanStage::Rejected;
    ActivityResult _result = ActivityResult::Failed;
    uint32 _guid = 0, _startedAt = 0, _progressAt = 0, _engagedAt = 0, _visits = 0;
    uint32 _wallStartedAt = 0, _deathAt = 0, _deaths = 0;
    uint32 _routeProgressAt = 0;
    float _routeX = 0, _routeY = 0, _routeZ = 0;
    bool _routeObserved = false;
    uint32 _safetyAt = 0, _safetyDelay = 5000;
    bool _recovering = false;
    bool _visitCounted = false, _safetyCooldown = false;
    bool _waitingSafety = false;
    bool _travelling = false, _engaged = false, _hadQuest = false, _rewarded = false;
    char const* _reason = "running";
};
}

std::unique_ptr<ActivityExecutor> MakeQuestExecutor(PlayerbotAI& ai, QuestPlanData const& data)
{
    return std::make_unique<QuestExecutor>(ai, data);
}
}
