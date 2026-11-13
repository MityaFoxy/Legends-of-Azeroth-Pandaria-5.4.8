#ifndef PLAYERBOT_GROUP_FOLLOW_FORMATION_H
#define PLAYERBOT_GROUP_FOLLOW_FORMATION_H

#include <cstddef>

namespace GroupFollowFormation
{
struct Offset
{
    float forward;
    float sideways;
};

inline Offset GetOffset(bool tank, std::size_t slot)
{
    // Stable rows, three yards apart, with the first tank directly in front.
    float const row = static_cast<float>(slot / 3) * 3.0f;
    float const sideways = static_cast<float>(static_cast<int>((slot + 1) % 3) - 1) * 3.0f;
    return {tank ? 5.0f + row : -4.0f - row, sideways};
}
}

#endif
