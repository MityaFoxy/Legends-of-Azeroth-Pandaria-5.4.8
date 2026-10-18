#pragma once

#include <cassert>
#include <cstdint>
#include <string>
#include "WorldSession.h"

using uint32 = uint32_t;

struct TestGuid
{
    uint32 value = 14;
    uint32 GetCounter() const { return value; }
    std::string ToString() const { return std::to_string(value); }
};

class Player
{
public:
    TestGuid guid;
    WorldSession session;
    bool hasSession = true;
    bool teleport = false;
    bool inWorld = true;
    bool removing = false;
    bool alive = true;
    bool combat = false;
    uint32 map = 0, instance = 0, phase = 1;

    TestGuid GetGUID() const { return guid; }
    std::string GetName() const { return "LifecycleTestBot"; }
    WorldSession* GetSession() { return hasSession ? &session : nullptr; }
    bool IsBeingTeleported() const { return teleport; }
    bool IsInWorld() const { return inWorld; }
    bool IsDuringRemoveFromWorld() const { return removing; }
    bool IsAlive() const { return alive; }
    bool IsInCombat() const { return combat; }
    uint32 GetMapId() const { assert(inWorld && !removing); return map; }
    uint32 GetInstanceId() const { assert(inWorld && !removing); return instance; }
    uint32 GetPhaseMask() const { assert(inWorld && !removing); return phase; }
};
