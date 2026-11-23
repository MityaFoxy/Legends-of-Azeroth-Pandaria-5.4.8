#ifndef _BOTLIFE_TYPES_H
#define _BOTLIFE_TYPES_H

#include <cstdint>

namespace BotLife
{
enum class ActivityType : uint8_t
{
    Free,
    Quest,
    Town,
    Rest,
    Leisure,
    Walk
};

enum class ActivityResult : uint8_t
{
    Running,
    Completed,
    TemporarilyBlocked,
    Failed
};
}

#endif
