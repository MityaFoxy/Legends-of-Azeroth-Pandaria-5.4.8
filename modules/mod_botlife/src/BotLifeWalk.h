#ifndef _BOTLIFE_WALK_H
#define _BOTLIFE_WALK_H

#include "BotLife.h"

namespace BotLife
{
std::unique_ptr<ActivityExecutor> CreateWalkExecutor(uint32_t duration);
}
#endif
