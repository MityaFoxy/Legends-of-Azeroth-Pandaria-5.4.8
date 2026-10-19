#include "BotLifeSafety.h"
#include <algorithm>
#include <cmath>

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
    for (LocalThreat const& threat : threats)
    {
        // Only the explicitly selected ordinary mob may be pulled. Even one
        // unrelated hostile on a route is a reason to choose another approach.
        if (target && threat.spawn == target && !threat.strong)
            continue;
        if (threat.aggressive && SegmentDistanceSquared(threat.position, from, to) <= threat.radius*threat.radius)
        {
            if (blocker)
                *blocker = &threat;
            return false;
        }
    }
    return true;
}
}
