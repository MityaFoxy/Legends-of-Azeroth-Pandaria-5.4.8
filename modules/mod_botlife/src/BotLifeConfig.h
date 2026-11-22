#ifndef _BOTLIFE_CONFIG_H
#define _BOTLIFE_CONFIG_H

#include <cstdint>

#include "BotLifeSchedule.h"

class Player;

namespace BotLife
{
bool IsEnabled();
bool IsEligible(Player* bot);
uint32_t StubActivityDuration();
bool IsSchedulerEnabled();
ScheduleSettings const& GetScheduleSettings();
}

#endif
