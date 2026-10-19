#include "BotLifeTravelTest.h"
#include "BotLifeMovement.h"
#include "BotLifeQuestAcquire.h"
#include "BotLifeQuestDiagnostic.h"
#include "BotLifeQuestRun.h"

#include <algorithm>
#include <sstream>
#include "CharacterCache.h"
#include "Chat.h"
#include "Config.h"
#include "Log.h"
#include "MotionMaster.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "Timer.h"

namespace BotLife
{
namespace
{
bool enabled = false;
uint32 botGuid = 0;
TravelTarget destination;

class TravelTestExecutor final : public ActivityExecutor
{
public:
    explicit TravelTestExecutor(PlayerbotAI& ai) : _movement(ai), _travel(_movement) { }
    ActivityType GetType() const override { return ActivityType::Free; }
    void Start(PlayerbotAI& ai) override
    {
        Player* bot = ai.GetBot();
        _target = destination;
        _target.instanceId = bot->GetInstanceId();
        _target.phaseMask = bot->GetPhaseMask();
        _travel.Start(_target);
        TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=start map={} from=({},{},{}) target=({},{},{})",
            botGuid, bot->GetMapId(), bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
            _target.x, _target.y, _target.z);
    }
    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        TravelStatus const status = _travel.Update(elapsed);
        _moved = _moved || _travel.ControlsMovement();
        _sample += std::min<uint32_t>(elapsed, 5000);
        if (_sample >= 5000 || status != _lastStatus)
        {
            Player* bot = ai.GetBot();
            TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=sample status={} failure={} attempts={} owned={} motion={} pos=({},{},{}) distance={} health={} failed_attempts={} progress_segments={}",
                botGuid, ToString(status), ToString(_travel.GetFailure()), _travel.GetAttempts(), _travel.ControlsMovement(),
                uint32(bot->GetMotionMaster()->GetCurrentMovementGeneratorType()), bot->GetPositionX(), bot->GetPositionY(),
                bot->GetPositionZ(), bot->GetExactDist(_target.x, _target.y, _target.z), bot->GetHealth(),
                _travel.GetFailedAttempts(), _travel.GetProgressSegments());
            _sample = 0;
            _lastStatus = status;
        }
        if (status == TravelStatus::Arrived)
            return ActivityResult::Completed;
        if (status == TravelStatus::Failed || status == TravelStatus::Cancelled)
            return ActivityResult::Failed;
        return ActivityResult::Running;
    }
    void Pause(PlayerbotAI& ai) override
    {
        bool const owned = _travel.ControlsMovement();
        _travel.Pause();
        ++_pauses;
        TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=pause owned_before={} owned_after={} motion_after={} victim={}",
            botGuid, owned, _travel.ControlsMovement(), uint32(ai.GetBot()->GetMotionMaster()->GetCurrentMovementGeneratorType()),
            ai.GetBot()->GetVictim() ? ai.GetBot()->GetVictim()->GetGUID().ToString() : "none");
    }
    bool Resume(PlayerbotAI&) override
    {
        bool const valid = _travel.Resume();
        if (valid)
            ++_resumes;
        TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=resume valid={}", botGuid, valid);
        return valid;
    }
    void Interrupt(PlayerbotAI&, InterruptReason reason) override
    {
        _travel.Cancel();
        TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=cancel reason={}", botGuid, ToString(reason));
    }
    void Finish(PlayerbotAI&, ActivityResult result) override
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife travel-test guid={} event=finish result={} failure={} moved={} pauses={} resumes={} attempts={} failed_attempts={} progress_segments={}",
            botGuid, ToString(result), ToString(_travel.GetFailure()), _moved, _pauses, _resumes, _travel.GetAttempts(),
            _travel.GetFailedAttempts(), _travel.GetProgressSegments());
        _travel.Cancel();
    }
    bool ControlsMovement() const override { return _travel.ControlsMovement(); }

private:
    NativeTravelMovement _movement;
    TravelExecutor _travel;
    TravelTarget _target;
    TravelStatus _lastStatus = TravelStatus::Idle;
    uint32 _sample = 0, _pauses = 0, _resumes = 0;
    bool _moved = false;
};

// Console-only, fixed-config target; never turns into a general bot-control API.
class TravelTestCommand final : public CommandScript
{
public:
    TravelTestCommand() : CommandScript("BotLifeTravelTestCommand") { }
    std::vector<ChatCommand> GetCommands() const override
    {
        return {{ "botlife-test-login", &Login, rbac::RBAC_PERM_COMMAND_NPCBOT, Trinity::ChatCommands::Console::Yes }};
    }
    static bool Login(ChatHandler* handler, char const* args)
    {
        // World-thread console only. Each configured QuestRun bot is requested once;
        // stable per-bot spacing avoids a synchronized five-login burst.
        static size_t nextQuestBot = 0;
        static uint32 lastQuestLogin = 0;
        std::vector<uint32_t> const questBots = GetQuestRunBotGuids();
        bool const questRun = IsQuestRunEnabled();
        uint32 const loginGuid = enabled ? botGuid :
            questRun ? (nextQuestBot < questBots.size() ? questBots[nextQuestBot] : 0) :
            IsQuestAcquireEnabled() ? GetQuestAcquireBotGuid() : GetQuestPlanBotGuid();
        if (handler->GetSession() || (args && *args) || !loginGuid ||
            !(questRun ? IsEligibleBot(loginGuid) : IsOnlyEligibleBot(loginGuid)) ||
            !sPlayerbotAIConfig->enabled || sPlayerbotAIConfig->randomBotAutologin)
        {
            handler->SendSysMessage("Requires console, an unrequested configured test bot and RandomBotAutologin=0.");
            return false;
        }
        if (questRun && nextQuestBot && GetMSTimeDiffToNow(lastQuestLogin) < 20000 + loginGuid % 7 * 1000)
        {
            handler->SendSysMessage("QuestRun login spacing: wait up to 26 seconds before requesting the next bot.");
            return false;
        }
        ObjectGuid const guid = ObjectGuid::Create<HighGuid::Player>(loginGuid);
        if (!sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid)))
        {
            handler->SendSysMessage("Configured character is not on a random-bot account.");
            return false;
        }
        sRandomPlayerbotMgr->AddPlayerBot(guid, 0);
        if (questRun)
        {
            ++nextQuestBot;
            lastQuestLogin = getMSTime();
        }
        handler->SendSysMessage("Requested login of the configured BotLife test bot; see playerbots.botlife log.");
        return true;
    }
};
}

void LoadTravelTestConfig()
{
    enabled = false;
    if (!sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.TravelTest.Enabled", false))
        return;
    botGuid = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.TravelTest.BotGuid", 0);
    std::istringstream input(sConfigMgr->GetStringDefault("AiPlayerbot.BotLife.TravelTest.Destination", ""));
    destination = {};
    bool const parsed = bool(input >> destination.mapId >> destination.x >> destination.y >> destination.z);
    input >> std::ws;
    if (!botGuid || !IsOnlyEligibleBot(botGuid) || !parsed || !input.eof() ||
        !Trinity::IsValidMapCoord(destination.x, destination.y, destination.z) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestRun.Enabled", false))
    {
        TC_LOG_ERROR("server.loading", "BotLife TravelTest rejected: require exactly one matching allowlisted GUID and destination 'map x y z'");
        return;
    }
    enabled = true;
    TC_LOG_WARN("server.loading", "BotLife single-run TravelTest enabled for guid={}; native movement will be issued", botGuid);
}

bool IsTravelTestEnabled() { return enabled; }

std::unique_ptr<ActivityExecutor> CreateTravelTestExecutor(PlayerbotAI& ai)
{
    if (!enabled || !ai.GetBot() || ai.GetBot()->GetGUID().GetCounter() != botGuid)
        return nullptr;
    return std::make_unique<TravelTestExecutor>(ai);
}

void RegisterTravelTestCommand() { new TravelTestCommand(); }
}
