#pragma once

#include <cstdint>
#include <memory>
#include <vector>
#include "G3D/Vector3.h"

class MovementGenerator;

// A short bypass may initially lead away from the goal. Remember its origins
// across MoveTo actions so another bypass cannot send the bot straight back.
struct NavigationDetourState
{
    std::uint32_t mapId = 0;
    std::uint32_t instanceId = 0;
    std::uint32_t updatedAt = 0;
    std::uint32_t nextVariant = 0;
    G3D::Vector3 goal;
    std::vector<G3D::Vector3> origins;
    // Tail of the last validated partial route. If an endpoint projects onto
    // the wrong nearby polygon on the next query, retreat along this known
    // geometry before trying the same goal again.
    std::vector<G3D::Vector3> continuation;
};

// Only movement issued by generic ground MoveTo belongs to this observer.
// Keep the requested goal separate from a partial route's reachable endpoint.
struct GroundMovementState
{
    // Optional caller identity, never an AI/world pointer. Recovery retains it;
    // every newly issued MoveTo revokes it, even for the same destination.
    std::shared_ptr<void const> owner;
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
