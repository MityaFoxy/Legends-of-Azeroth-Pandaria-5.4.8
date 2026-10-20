#include "BotLifeSafety.h"
#include <algorithm>
#include <cmath>
#include <limits>

namespace BotLife
{
float SegmentDistanceSquared(SafetyPoint p, SafetyPoint a, SafetyPoint b)
{
    float const dx = b.x-a.x, dy = b.y-a.y, dz = b.z-a.z;
    float const length = dx*dx + dy*dy + dz*dz;
    float const t = length > 0 ? std::clamp(((p.x-a.x)*dx + (p.y-a.y)*dy + (p.z-a.z)*dz) / length, 0.0f, 1.0f) : 0;
    float const x = p.x-a.x-t*dx, y = p.y-a.y-t*dy, z = p.z-a.z-t*dz;
    return x*x+y*y+z*z;
}

bool SafeThreatSegment(std::vector<LocalThreat> const& threats, SafetyPoint from, SafetyPoint to, uint32_t target,
    LocalThreat const** blocker)
{
    if (blocker)
        *blocker = nullptr;
    if (!std::isfinite(from.x+from.y+from.z+to.x+to.y+to.z))
        return false;
    LocalThreat const* first = nullptr;
    float firstEntry = std::numeric_limits<float>::infinity();
    float const dx = to.x-from.x, dy = to.y-from.y, dz = to.z-from.z;
    float const length = std::sqrt(dx*dx + dy*dy + dz*dz);
    for (LocalThreat const& threat : threats)
    {
        // Combat assessment admits the selected opponent separately. Geometry
        // must still reject every unrelated hostile, regardless of its rank.
        if (target && threat.spawn == target)
            continue;
        if (threat.aggressive && SegmentDistanceSquared(threat.position, from, to) <= threat.radius*threat.radius)
        {
            // Grid iteration order is not travel order. Clear the first aggro
            // boundary on this segment, not an arbitrary farther opponent.
            float entry = 0;
            if (length > 0)
            {
                float const x = threat.position.x-from.x, y = threat.position.y-from.y, z = threat.position.z-from.z;
                float const along = (x*dx + y*dy + z*dz) / length;
                float const perpendicularSquared = std::max(0.0f, x*x+y*y+z*z-along*along);
                entry = std::max(0.0f, along - std::sqrt(std::max(0.0f, threat.radius*threat.radius-perpendicularSquared)));
            }
            if (!first || entry < firstEntry || (entry == firstEntry && threat.spawn < first->spawn))
            {
                first = &threat;
                firstEntry = entry;
            }
        }
    }
    if (blocker)
        *blocker = first;
    return !first;
}
}
