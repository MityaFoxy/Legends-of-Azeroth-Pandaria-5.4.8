#include "BotLife.h"
#include "BotLifeTravelTest.h"
#include "BotLifeQuestDiagnostic.h"

#include <boost/filesystem.hpp>
#include <memory>
#include <string>

#include "Config.h"
#include "Log.h"
#include "PlayerbotAIExtension.h"
#include "ScriptMgr.h"

#ifndef _BOTLIFE_CONFIG
# define _BOTLIFE_CONFIG "botlife.conf"
#endif

namespace
{
std::unique_ptr<PlayerbotAIExtension> CreateBotLifeExtension()
{
    return std::make_unique<BotLife::ActivityContext>(&BotLife::CreateExecutor,
        BotLife::IsTravelTestEnabled() ? &BotLife::CreateTravelTestExecutor :
        BotLife::IsQuestPlanEnabled() ? &BotLife::CreateQuestPlanExecutor : nullptr);
}

class BotLifeWorldScript final : public WorldScript
{
public:
    BotLifeWorldScript() : WorldScript("BotLifeWorldScript") { }

    void OnConfigLoad(bool reloaded) override
    {
        if (!reloaded)
        {
            std::string const configPath = boost::filesystem::absolute(_BOTLIFE_CONFIG).generic_string();
            std::string error;
            if (!sConfigMgr->LoadAdditionalFile(configPath, true, error))
            {
                TC_LOG_WARN("server.loading", "BotLife config was not loaded from {}: {}. Defaults will be used",
                    configPath, error);
            }
        }

        BotLife::LoadConfig();
        BotLife::LoadTravelTestConfig();
        if (!reloaded)
            BotLife::LoadQuestPlanConfig();
    }

    void OnStartup() override { BotLife::InitializeQuestPlanData(); }
};
}

void AddSC_mod_botlife()
{
    sPlayerbotAIExtensionRegistry->Register(&CreateBotLifeExtension);
    new BotLifeWorldScript();
    BotLife::RegisterTravelTestCommand();
}
