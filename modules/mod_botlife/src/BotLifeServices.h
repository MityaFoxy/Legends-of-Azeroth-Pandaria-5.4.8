#ifndef _BOTLIFE_SERVICES_H
#define _BOTLIFE_SERVICES_H

#include "BotLife.h"
#include "BotLifeSchedule.h"

namespace BotLife
{
ScheduleNeeds ReadScheduleNeeds(PlayerbotAI& ai);
std::unique_ptr<ActivityExecutor> CreateServiceExecutor(ActivityType activity, uint32_t duration);
}
#endif
