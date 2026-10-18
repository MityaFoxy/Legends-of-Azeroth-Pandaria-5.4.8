#pragma once

#include <string>

struct TestConfig
{
    bool enabled = true;
    std::string guids = "14,9";
    int duration = 1000;
    bool GetBoolDefault(char const*, bool) const { return enabled; }
    std::string GetStringDefault(char const*, char const*) const { return guids; }
    int GetIntDefault(char const*, int) const { return duration; }
};

inline TestConfig testConfig;
inline TestConfig* sConfigMgr = &testConfig;
