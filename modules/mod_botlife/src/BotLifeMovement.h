#ifndef _BOTLIFE_MOVEMENT_H
#define _BOTLIFE_MOVEMENT_H

#include "BotLifeTravel.h"
#include "MovementActions.h"
#include <memory>

namespace BotLife
{
class NativeTravelMovement final : public TravelMovement, private MovementAction
{
public:
    explicit NativeTravelMovement(PlayerbotAI& ai);
    NativeTravelMovement(NativeTravelMovement const&) = delete;
    NativeTravelMovement& operator=(NativeTravelMovement const&) = delete;
    bool IsValid(TravelTarget const& target) const override;
    bool IsBlocked() override;
    bool HasArrived(TravelTarget const& target) const override;
    TravelMoveResult Move(TravelTarget const& target) override;
    TravelMotion Poll() const override;
    bool OwnsMovement() const override;
    void Release() override;

private:
    std::shared_ptr<void const> _owner;
    TravelTarget _target;
    float _endX = 0, _endY = 0, _endZ = 0;
};
}
#endif
