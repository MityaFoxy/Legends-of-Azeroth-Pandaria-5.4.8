#pragma once

#include <cstring>
#include <string>

struct TestConfig
{
    bool enabled = true;
    bool scheduler = false;
    std::string guids = "14,9";
    int duration = 1000;
    bool GetBoolDefault(char const* name, bool fallback) const
    {
        if (!std::strcmp(name, "AiPlayerbot.BotLife.Enabled"))
            return enabled;
        if (!std::strcmp(name, "AiPlayerbot.BotLife.Scheduler.Enabled"))
            return scheduler;
        return fallback;
    }
    std::string GetStringDefault(char const*, char const*) const { return guids; }
    int GetIntDefault(char const* name, int fallback) const
    {
        return !std::strcmp(name, "AiPlayerbot.BotLife.StubActivityDuration") ? duration : fallback;
    }
};

inline TestConfig testConfig;
inline TestConfig* sConfigMgr = &testConfig;
