#include "BotLifeQuestAcquire.h"
#include "BotLifeQuestData.h"
#include "BotLifeQuestInteraction.h"
#include "BotLifeMovement.h"

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"

namespace BotLife
{
namespace
{
bool enabled = false;
uint32 botGuid = 0, questId = 0;
// Published once at startup. AI threads only read these owned value snapshots.
QuestPlanData catalog;

class QuestAcquireExecutor final : public ActivityExecutor
{
public:
    explicit QuestAcquireExecutor(PlayerbotAI& ai) : _movement(ai), _travel(_movement) { }
    ActivityType GetType() const override { return ActivityType::Quest; }
    void Start(PlayerbotAI& ai) override
    {
        Player* bot = ai.GetBot();
        if (!bot)
            return;
        if (char const* reason = QuestAcquireRejection(*bot, catalog))
        {
            Fail(reason);
            return;
        }
        QuestPlan const plan = BuildQuestPlan(catalog, ReadQuestPlayer(catalog, *bot));
        if (plan.stage != QuestPlanStage::Acquire || !plan.starter)
        {
            Fail(ToString(plan.reason));
            return;
        }
        _giver = *plan.starter;
        _target = {_giver.mapId, bot->GetInstanceId(), bot->GetPhaseMask(), _giver.x, _giver.y, _giver.z, 1.0f};
        _travel.Start(_target);
        _result = ActivityResult::Running;
        _reason = "travelling";
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=start giver={} entry={} target=({},{},{})",
            botGuid, questId, _giver.guid, _giver.entry, _giver.x, _giver.y, _giver.z);
    }
    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        if (_result != ActivityResult::Running)
            return _result;
        if (!IsOnlyEligibleBot(botGuid) || !ai.GetBot() || !_movement.IsValid(_target))
            return Fail("invalid-context");
        if (char const* reason = QuestAcquireRejection(*ai.GetBot(), catalog))
            return Fail(reason);
        TravelStatus const status = _travel.Update(elapsed);
        if (status == TravelStatus::Failed || status == TravelStatus::Cancelled)
            return Fail(ToString(_travel.GetFailure()));
        if (status != TravelStatus::Arrived)
            return ActivityResult::Running;
        // Re-resolve the real NPC and all native interaction gates at arrival.
        // A missing/dead/moved giver is a bounded failure, not remote acceptance.
        _travel.Cancel();
        _accepted = TryAcceptQuest(*ai.GetBot(), catalog, _giver, _reason);
        _result = _accepted ? ActivityResult::Completed : ActivityResult::Failed;
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=interaction accepted={} reason={}",
            botGuid, questId, _accepted, _reason);
        return _result;
    }
    void Pause(PlayerbotAI&) override
    {
        _travel.Pause();
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=pause", botGuid, questId);
    }
    bool Resume(PlayerbotAI& ai) override
    {
        if (_result != ActivityResult::Running || !IsOnlyEligibleBot(botGuid) || !ai.GetBot())
            return false;
        if (char const* reason = QuestAcquireRejection(*ai.GetBot(), catalog))
        {
            Fail(reason);
            return false;
        }
        bool const valid = _travel.Resume();
        if (!valid)
            Fail("invalid-resume");
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=resume valid={}", botGuid, questId, valid);
        return valid;
    }
    void Interrupt(PlayerbotAI&, InterruptReason reason) override
    {
        Fail(ToString(reason));
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=cancel reason={}",
            botGuid, questId, _reason);
    }
    void Finish(PlayerbotAI&, ActivityResult result) override
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife quest-acquire guid={} quest={} event=finish result={} accepted={} reason={} attempts={} failed_attempts={} progress_segments={}",
            botGuid, questId, ToString(result), _accepted, _reason, _travel.GetAttempts(),
            _travel.GetFailedAttempts(), _travel.GetProgressSegments());
        _travel.Cancel();
    }
    bool ControlsMovement() const override { return _travel.ControlsMovement(); }

private:
    ActivityResult Fail(char const* reason)
    {
        _reason = reason;
        _result = ActivityResult::Failed;
        _travel.Cancel();
        return _result;
    }
    NativeTravelMovement _movement;
    TravelExecutor _travel;
    QuestSpawn _giver;
    TravelTarget _target;
    ActivityResult _result = ActivityResult::Failed;
    char const* _reason = "not-started";
    bool _accepted = false;
};
}

void LoadQuestAcquireConfig()
{
    enabled = false;
    if (!sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestAcquire.Enabled", false))
        return;
    int32 const configuredBot = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestAcquire.BotGuid", 0);
    int32 const configuredQuest = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestAcquire.QuestId", 0);
    if (configuredBot <= 0 || configuredQuest <= 0 || !IsOnlyEligibleBot(uint32(configuredBot)) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.TravelTest.Enabled", false) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestPlan.Enabled", false) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestRun.Enabled", false))
    {
        TC_LOG_ERROR("server.loading", "BotLife QuestAcquire rejected: require one matching allowlisted bot, positive QuestId, TravelTest and QuestPlan disabled");
        return;
    }
    botGuid = uint32(configuredBot);
    questId = uint32(configuredQuest);
    enabled = true;
}

void InitializeQuestAcquireData()
{
    if (!enabled)
        return;
    catalog = LoadQuestPlanData(questId);
    TC_LOG_WARN("server.loading", "BotLife one-shot QuestAcquire guid={} quest={} catalog={}; native quest acceptance enabled, no objective execution/turn-in",
        botGuid, questId, ToString(catalog.error));
}

bool IsQuestAcquireEnabled() { return enabled; }
uint32_t GetQuestAcquireBotGuid() { return enabled ? botGuid : 0; }

std::unique_ptr<ActivityExecutor> CreateQuestAcquireExecutor(PlayerbotAI& ai)
{
    if (!enabled || !IsOnlyEligibleBot(botGuid) || !ai.GetBot() || ai.GetBot()->GetGUID().GetCounter() != botGuid)
        return nullptr;
    return std::make_unique<QuestAcquireExecutor>(ai);
}
}
