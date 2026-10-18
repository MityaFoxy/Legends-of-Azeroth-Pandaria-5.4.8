#ifndef _BOTLIFE_TRAVEL_TEST_H
#define _BOTLIFE_TRAVEL_TEST_H

#include "BotLife.h"

namespace BotLife
{
void LoadTravelTestConfig();
bool IsTravelTestEnabled();
std::unique_ptr<ActivityExecutor> CreateTravelTestExecutor(PlayerbotAI& ai);
void RegisterTravelTestCommand();
}
#endif
