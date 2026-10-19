#ifndef _BOTLIFE_PREPARATION_H
#define _BOTLIFE_PREPARATION_H

#include "BotLifeMovement.h"
#include "BotLifeReadiness.h"
#include "BotLifeSafety.h"

namespace BotLife
{
enum class PreparationResult { Ready, Waiting, Failed };

// A quest's bounded service detour, not a second AI. Inventory, money, natural
// regeneration and NPC interaction all remain native server operations.
class QuestPreparation
{
public:
    QuestPreparation(PlayerbotAI& ai, QuestSafety& safety);
    PreparationResult Update(uint32_t elapsed);
    bool NeedsService() const;
    void Pause();
    bool ControlsMovement() const { return _travel.ControlsMovement(); }
    bool HoldsNonCombat() const { return _holding; }
    char const* Reason() const { return _reason; }
private:
    PreparationResult Rest(Readiness const& readiness);
    PreparationResult Repair(uint32_t elapsed);
    void Report(Readiness const& readiness, char const* reason);
    Player& _bot;
    QuestSafety& _safety;
    NativeTravelMovement _movement;
    TravelExecutor _travel;
    std::optional<QuestSpawn> _vendor;
    uint64_t _waitMs = 0;
    bool _resting = false, _sitting = false, _holding = false;
    char const* _reason = "unobserved";
};
}
#endif
