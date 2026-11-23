#include "BotLifeWalk.h"
#include "BotLifeMovement.h"
#include "BotLifeSafety.h"
#include "BotLifeServices.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Log.h"
#include "Map.h"
#include "Player.h"
#include "PlayerbotAI.h"

#include <algorithm>
#include <list>
#include <limits>

namespace BotLife
{
namespace
{
class WalkExecutor final : public ActivityExecutor
{
public:
    explicit WalkExecutor(uint32_t duration) : _duration(duration) { }
    ActivityType GetType() const override { return ActivityType::Walk; }

    void Start(PlayerbotAI& ai) override
    {
        _bot = ai.GetBot();
        _elapsed = 0;
        _result = ActivityResult::Running;
        if (!_bot || !_bot->GetMap() || _bot->GetMap()->Instanceable() || !ReadScheduleNeeds(ai).canQuest)
        {
            End(ActivityResult::Failed, "invalid-walk-context");
            return;
        }
        _safety = std::make_unique<QuestSafety>(*_bot);
        _movement = std::make_unique<NativeTravelMovement>(ai, [this] { return _safety->RouteSafe(); });
        _travel = std::make_unique<TravelExecutor>(*_movement);
        auto check = [this](Creature* npc)
        {
            return Eligible(npc) && _bot->IsWithinDistInMap(npc, 100) && !_bot->IsWithinDistInMap(npc, 25);
        };
        std::list<Creature*> landmarks;
        Trinity::CreatureListSearcher<decltype(check)> searcher(_bot, landmarks, check);
        Cell::VisitAllObjects(_bot, searcher, 100); // Loaded grids only; once per activity.
        auto rank = [seed = _bot->GetGUID().GetCounter()](uint32_t spawn)
        {
            uint32_t value = spawn ^ seed;
            value ^= value >> 16;
            value *= 0x7feb352du;
            value ^= value >> 15;
            return value;
        };
        landmarks.sort([&rank](Creature* left, Creature* right)
        {
            uint32_t const a = rank(left->GetSpawnId()), b = rank(right->GetSpawnId());
            return a == b ? left->GetSpawnId() < right->GetSpawnId() : a < b;
        });
        uint32_t checked = 0;
        for (Creature* npc : landmarks)
        {
            if (++checked > 8)
                break; // Bound expensive path/safety queries, even in crowded towns.
            QuestSpawn candidate{npc->GetSpawnId(), npc->GetEntry(), _bot->GetMapId(), npc->GetPhaseMask(),
                npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()};
            if (!_safety->CanApproach(candidate))
                continue;
            _landmark = candidate;
            _target = {_bot->GetMapId(), _bot->GetInstanceId(), _bot->GetPhaseMask(),
                candidate.x, candidate.y, candidate.z, 4.0f};
            if (!_movement->IsValid(_target))
                continue;
            TravelLimits limits;
            limits.timeoutMs = _duration;
            _travel->Start(_target, limits);
            TC_LOG_INFO("playerbots.botlife", "BotLife walk guid={} event=start landmark={} budget_ms={}",
                _bot->GetGUID().GetCounter(), candidate.guid, _duration);
            return;
        }
        End(ActivityResult::Failed, "no-safe-local-landmark");
    }

    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        if (_result != ActivityResult::Running)
            return _result;
        _elapsed += std::min(elapsed, std::numeric_limits<uint32_t>::max() - _elapsed);
        if (_elapsed >= _duration)
            return End(ActivityResult::Failed, "walk-timeout");
        if (!ReadScheduleNeeds(ai).canQuest || !ValidLandmark())
            return End(ActivityResult::Failed, "walk-context-or-landmark-changed");
        if (!_safety->CanApproach(_landmark) || (_travel->ControlsMovement() && !_safety->RouteSafe()))
            return End(ActivityResult::Failed, "walk-unsafe-route");
        TravelStatus const status = _travel->Update(elapsed);
        if (status == TravelStatus::Arrived)
            return End(ActivityResult::Completed, "walk-arrived");
        if (status == TravelStatus::Failed || status == TravelStatus::Cancelled)
            return End(ActivityResult::Failed, ToString(_travel->GetFailure()));
        return status == TravelStatus::TemporarilyBlocked ? ActivityResult::TemporarilyBlocked : ActivityResult::Running;
    }

    void Pause(PlayerbotAI&) override { if (_travel) _travel->Pause(); }
    bool Resume(PlayerbotAI& ai) override
    {
        if (_result == ActivityResult::Running && (!ReadScheduleNeeds(ai).canQuest ||
            !ValidLandmark() || !_safety->CanApproach(_landmark) || !_travel->Resume()))
            End(ActivityResult::Failed, "walk-resume-invalid");
        // Report the failure on Update so policy retains outing cooldown and
        // applies walk backoff. Returning false would discard the whole context.
        return true;
    }
    void Interrupt(PlayerbotAI&, InterruptReason) override { End(ActivityResult::Failed, "interrupted"); }
    void Finish(PlayerbotAI&, ActivityResult) override { if (_travel) _travel->Cancel(); }
    bool ControlsMovement() const override { return _travel && _travel->ControlsMovement(); }
    bool HoldsNonCombat() const override { return _result == ActivityResult::Running; }

private:
    bool Eligible(Creature* npc) const
    {
        return npc && npc->GetSpawnId() && npc->IsAlive() && !npc->IsInCombat() &&
            _bot->IsFriendlyTo(npc) && _bot->CanSeeOrDetect(npc);
    }
    bool ValidLandmark() const
    {
        if (!_movement->IsValid(_target))
            return false;
        Creature* npc = _bot->GetMap()->GetCreatureBySpawnId(_landmark.guid);
        if (!Eligible(npc) || npc->GetEntry() != _landmark.entry)
            return false;
        float const dx = npc->GetPositionX() - _landmark.x;
        float const dy = npc->GetPositionY() - _landmark.y;
        float const dz = npc->GetPositionZ() - _landmark.z;
        return dx * dx + dy * dy + dz * dz <= 4.0f; // Moving NPCs are not chased.
    }
    ActivityResult End(ActivityResult result, char const* reason)
    {
        if (_travel)
            _travel->Cancel();
        _result = result;
        TC_LOG_INFO("playerbots.botlife", "BotLife walk guid={} event=finish result={} reason={} duration_ms={}",
            _bot ? _bot->GetGUID().GetCounter() : 0, ToString(result), reason, _elapsed);
        return result;
    }

    Player* _bot = nullptr; // Owner's map-thread context, never a different bot/NPC.
    uint32_t _duration, _elapsed = 0;
    ActivityResult _result = ActivityResult::Failed;
    QuestSpawn _landmark;
    TravelTarget _target;
    std::unique_ptr<QuestSafety> _safety;
    std::unique_ptr<NativeTravelMovement> _movement;
    std::unique_ptr<TravelExecutor> _travel;
};
}

std::unique_ptr<ActivityExecutor> CreateWalkExecutor(uint32_t duration)
{
    return std::make_unique<WalkExecutor>(duration);
}
}
