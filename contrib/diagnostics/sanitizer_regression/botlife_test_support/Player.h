#pragma once

#include <cassert>
#include <cstdint>
#include <string>
#include "WorldSession.h"

using uint32 = uint32_t;
constexpr uint32 PLAYER_FLAGS_GHOST = 16;
enum Powers : uint8_t { POWER_MANA, POWER_RAGE };
enum UnitStandStateType : uint8_t { UNIT_STAND_STATE_STAND, UNIT_STAND_STATE_SIT };

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
    bool teleportBySpell = false;
    bool nearTeleport = true, ghost = false, corpse = false;
    float health = 100;
    float mana = 100;
    Powers powerType = POWER_MANA;
    bool sitting = false;
    bool inWorld = true;
    bool removing = false;
    bool alive = true;
    bool combat = false;
    uint32 map = 0, instance = 0, phase = 1;

    TestGuid GetGUID() const { return guid; }
    std::string GetName() const { return "LifecycleTestBot"; }
    WorldSession* GetSession() { return hasSession ? &session : nullptr; }
    bool IsBeingTeleported() const { return teleport; }
    bool IsBeingTeleportedBySpell() const { return teleportBySpell; }
    bool IsBeingTeleportedNear() const { return teleport && nearTeleport; }
    bool HasPlayerFlag(uint32) const { return ghost; }
    Player* GetCorpse() { return corpse ? this : nullptr; }
    float GetHealthPct() const { return health; }
    Powers GetPowerType() const { return powerType; }
    uint32 GetMaxPower(Powers) const { return 100; }
    float GetPowerPct(Powers) const { return mana; }
    bool IsSitState() const { return sitting; }
    void SetStandState(UnitStandStateType state) { sitting = state == UNIT_STAND_STATE_SIT; }
    bool IsInWorld() const { return inWorld; }
    bool IsDuringRemoveFromWorld() const { return removing; }
    bool IsAlive() const { return alive; }
    bool IsInCombat() const { return combat; }
    uint32 GetMapId() const { assert(inWorld && !removing); return map; }
    uint32 GetInstanceId() const { assert(inWorld && !removing); return instance; }
    uint32 GetPhaseMask() const { assert(inWorld && !removing); return phase; }
};
