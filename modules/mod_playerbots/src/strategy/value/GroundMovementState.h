#pragma once

#include <cstdint>
#include "G3D/Vector3.h"

class MovementGenerator;

// Only movement issued by generic ground MoveTo belongs to this observer.
// Keep the requested goal separate from a partial route's reachable endpoint.
struct GroundMovementState
{
    bool tracked = false;
    bool active = false;
    bool exhausted = false;
    bool recovering = false;
    bool normalOnly = false;
    bool backwards = false;
    std::uint32_t mapId = 0;
    std::uint32_t instanceId = 0;
    std::uint32_t splineId = 0;
    std::uint32_t attempts = 0;
    std::uint32_t idleMs = 0;
    MovementGenerator const* generator = nullptr; // identity only; never dereferenced
    G3D::Vector3 goal;
    G3D::Vector3 anchor;
    G3D::Vector3 endpoint;
    G3D::Vector3 recoveryStart;

    bool Matches(std::uint32_t map, std::uint32_t instance, G3D::Vector3 const& target) const
    {
        return tracked && mapId == map && instanceId == instance && (goal - target).length() <= 0.5f;
    }
};
