#include "BotLifeScheduledQuest.h"

#include "BotLifeConfig.h"
#include "BotLifeQuestData.h"
#include "BotLifeQuestExecutor.h"
#include "BotLifeQuestSelection.h"
#include "BotLifeServices.h"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "Util.h"

namespace BotLife
{
namespace
{
std::vector<uint32_t> configuredQuests;
std::map<uint32_t, QuestPlanData> catalogs;
bool enabled = false;

double DistanceSquared(QuestSpawn const& target, QuestPlayerSnapshot const& player)
{
    double const dx = double(target.x) - player.x;
    double const dy = double(target.y) - player.y;
    double const dz = double(target.z) - player.z;
    return dx * dx + dy * dy + dz * dz;
}

double PlanDistanceSquared(QuestPlan const& plan, QuestPlayerSnapshot const& player)
{
    if (plan.stage == QuestPlanStage::Acquire && plan.starter)
        return DistanceSquared(*plan.starter, player);
    if (plan.stage == QuestPlanStage::TurnIn && plan.ender)
        return DistanceSquared(*plan.ender, player);
    if (plan.stage == QuestPlanStage::Hunt)
    {
        double best = std::numeric_limits<double>::infinity();
        for (QuestObjectivePlan const& objective : plan.objectives)
            if (objective.remaining && objective.candidate)
                best = std::min(best, DistanceSquared(*objective.candidate, player));
        return best;
    }
    return plan.stage == QuestPlanStage::AwaitCompletion ? 0.0 :
        std::numeric_limits<double>::infinity();
}

QuestPlanData const* SelectCatalog(Player& bot, char const*& reason)
{
    std::vector<ScheduledQuestCandidate> candidates;
    candidates.reserve(catalogs.size());
    bool activeQuest = false;
    for (auto const& [questId, data] : catalogs)
    {
        QuestPlayerSnapshot const player = ReadQuestPlayer(data, bot);
        activeQuest |= player.progress == QuestProgress::Active || player.progress == QuestProgress::Complete;
        QuestPlan const plan = BuildQuestPlan(data, player);
        candidates.push_back({questId, plan.stage, PlanDistanceSquared(plan, player)});
    }
    std::optional<uint32_t> const selected = SelectScheduledQuest(candidates, !activeQuest);
    if (!selected)
    {
        reason = activeQuest ? "active-unplannable" : "no-eligible-candidate";
        return nullptr;
    }
    auto const it = catalogs.find(*selected);
    reason = it == catalogs.end() ? "catalog-missing" : "selected";
    return it == catalogs.end() ? nullptr : &it->second;
}

class ScheduledQuestExecutor final : public ActivityExecutor
{
public:
    explicit ScheduledQuestExecutor(uint32_t duration) : _duration(duration) { }

    ActivityType GetType() const override { return ActivityType::Quest; }

    void Start(PlayerbotAI& ai) override
    {
        _elapsed = 0;
        _result = ActivityResult::Failed;
        Player* bot = ai.GetBot();
        char const* selection = bot ? "no-eligible-candidate" : "missing-bot";
        QuestPlanData const* data = bot ? SelectCatalog(*bot, selection) : nullptr;
        if (!data)
        {
            TC_LOG_INFO("playerbots.botlife", "BotLife scheduled-quest guid={} event=select result=none reason={}",
                bot ? bot->GetGUID().GetCounter() : 0, selection);
            return;
        }
        _questId = data->questId;
        _inner = MakeQuestExecutor(ai, *data);
        if (!_inner)
            return;
        _inner->Start(ai);
        _result = ActivityResult::Running;
        TC_LOG_INFO("playerbots.botlife", "BotLife scheduled-quest guid={} event=select quest={} budget_ms={}",
            bot->GetGUID().GetCounter(), _questId, _duration);
    }

    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        if (_result != ActivityResult::Running || !_inner)
            return _result;
        uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
        _elapsed += std::min(elapsed, available);
        if (_elapsed >= _duration)
        {
            _inner->Interrupt(ai, InterruptReason::BudgetExpired);
            TC_LOG_INFO("playerbots.botlife", "BotLife scheduled-quest guid={} quest={} event=budget-expired elapsed_ms={}",
                ai.GetBot() ? ai.GetBot()->GetGUID().GetCounter() : 0, _questId, _elapsed);
            return _result = ActivityResult::Failed;
        }
        ActivityResult const result = _inner->Update(ai, elapsed);
        if (result == ActivityResult::Completed || result == ActivityResult::Failed)
            _result = result;
        return result;
    }

    void Pause(PlayerbotAI& ai) override { if (_inner) _inner->Pause(ai); }
    bool Resume(PlayerbotAI& ai) override { return _inner && _result == ActivityResult::Running && _inner->Resume(ai); }
    bool SuspendForDeath(PlayerbotAI& ai) override { return _inner && _inner->SuspendForDeath(ai); }
    bool IsDeathRecoveryExpired() const override { return _inner && _inner->IsDeathRecoveryExpired(); }

    void Interrupt(PlayerbotAI& ai, InterruptReason reason) override
    {
        if (_inner && _result == ActivityResult::Running)
            _inner->Interrupt(ai, reason);
        _result = ActivityResult::Failed;
    }

    void Finish(PlayerbotAI& ai, ActivityResult result) override
    {
        if (_inner)
            _inner->Finish(ai, result);
        _inner.reset();
    }

    bool ControlsMovement() const override { return _inner && _inner->ControlsMovement(); }
    bool HoldsNonCombat() const override { return _inner && _inner->HoldsNonCombat(); }

private:
    std::unique_ptr<ActivityExecutor> _inner;
    uint32_t _duration = 0;
    uint32_t _elapsed = 0;
    uint32_t _questId = 0;
    ActivityResult _result = ActivityResult::Failed;
};
}

void LoadScheduledQuestConfig()
{
    configuredQuests.clear();
    catalogs.clear();
    enabled = false;
    if (!IsSchedulerEnabled())
        return;

    std::set<uint32_t> unique;
    std::string const list = sConfigMgr->GetStringDefault("AiPlayerbot.BotLife.Scheduler.QuestIds", "");
    for (std::string_view token : Trinity::Tokenize(list, ',', false))
    {
        uint32_t questId = 0;
        auto const parsed = std::from_chars(token.data(), token.data() + token.size(), questId);
        if (parsed.ec != std::errc() || parsed.ptr != token.data() + token.size() || !questId)
        {
            TC_LOG_ERROR("server.loading", "BotLife scheduled quest catalog rejected: invalid QuestIds token '{}'", token);
            configuredQuests.clear();
            return;
        }
        unique.insert(questId);
    }
    if (unique.size() > 32)
    {
        TC_LOG_ERROR("server.loading", "BotLife scheduled quest catalog rejected: {} ids exceeds limit 32", unique.size());
        return;
    }
    configuredQuests.assign(unique.begin(), unique.end());
    enabled = !configuredQuests.empty();
    if (IsSchedulerEnabled() && !enabled)
        TC_LOG_WARN("server.loading", "BotLife scheduler has no QuestIds; QUEST remains a non-invasive timed window");
}

void InitializeScheduledQuestData()
{
    if (!enabled)
        return;
    for (uint32_t questId : configuredQuests)
    {
        QuestPlanData data = LoadQuestPlanData(questId);
        TC_LOG_INFO("server.loading", "BotLife scheduled quest catalog quest={} result={}", questId, ToString(data.error));
        catalogs.emplace(questId, std::move(data));
    }
}

bool IsScheduledQuestEnabled() { return enabled && !catalogs.empty() && IsSchedulerEnabled(); }

std::unique_ptr<ActivityExecutor> CreateScheduledExecutor(ActivityType activity, uint32_t duration)
{
    if (activity == ActivityType::Quest && IsScheduledQuestEnabled())
        return std::make_unique<ScheduledQuestExecutor>(duration);
    if (IsSchedulerEnabled() && (activity == ActivityType::Town || activity == ActivityType::Leisure))
        return CreateServiceExecutor(activity, duration);
    return CreateExecutor(activity, duration);
}
}
