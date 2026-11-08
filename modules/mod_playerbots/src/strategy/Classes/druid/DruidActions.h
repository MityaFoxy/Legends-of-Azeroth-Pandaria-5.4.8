/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#ifndef _PLAYERBOT_DRUIDACTIONS_H
#define _PLAYERBOT_DRUIDACTIONS_H

#include "GenericSpellActions.h"
#include "DruidControlActions.h"
#include "SharedDefines.h"

class PlayerbotAI;
class Unit;

class CastFaerieFireAction : public CastDebuffSpellAction
{
public:
    CastFaerieFireAction(PlayerbotAI* botAI) : CastDebuffSpellAction(botAI, "faerie fire") {}
};

class CastFaerieFireFeralAction : public CastDebuffSpellAction
{
public:
    CastFaerieFireFeralAction(PlayerbotAI* botAI) : CastDebuffSpellAction(botAI, "faerie fire") {}
    std::string const getName() override { return "faerie fire (feral)"; }
};

class CastRejuvenationAction : public CastHealingSpellAction
{
public:
    CastRejuvenationAction(PlayerbotAI* botAI) : CastHealingSpellAction(botAI, "rejuvenation") {}
};

class CastRegrowthAction : public CastHealingSpellAction
{
public:
    CastRegrowthAction(PlayerbotAI* botAI) : CastHealingSpellAction(botAI, "regrowth") {}
};

class CastHealingTouchAction : public CastHealingSpellAction
{
public:
    CastHealingTouchAction(PlayerbotAI* botAI) : CastHealingSpellAction(botAI, "healing touch") {}
};

class CastRejuvenationOnPartyAction : public HealPartyMemberAction
{
public:
    CastRejuvenationOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "rejuvenation", 15.0f, HealingManaEfficiency::VERY_HIGH)
    {
    }
};

class CastRegrowthOnPartyAction : public HealPartyMemberAction
{
public:
    CastRegrowthOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "regrowth", 35.0f, HealingManaEfficiency::HIGH)
    {
    }
};

class CastHealingTouchOnPartyAction : public HealPartyMemberAction
{
public:
    CastHealingTouchOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "healing touch", 50.0f, HealingManaEfficiency::LOW)
    {
    }
};

class CastReviveAction : public ResurrectPartyMemberAction
{
public:
    CastReviveAction(PlayerbotAI* botAI) : ResurrectPartyMemberAction(botAI, "revive") {}

    NextAction** getPrerequisites() override;
};

class CastRebirthAction : public ResurrectPartyMemberAction
{
public:
    CastRebirthAction(PlayerbotAI* botAI) : ResurrectPartyMemberAction(botAI, "rebirth") {}

    NextAction** getPrerequisites() override;
    bool isUseful() override;
};

class CastMarkOfTheWildAction : public CastBuffSpellAction
{
public:
    CastMarkOfTheWildAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "mark of the wild") {}
};

class CastMarkOfTheWildOnPartyAction : public BuffOnPartyAction
{
public:
    CastMarkOfTheWildOnPartyAction(PlayerbotAI* botAI) : BuffOnPartyAction(botAI, "mark of the wild") {}
    Value<Unit*>* GetTargetValue() override;
    bool Execute(Event event) override;
};

class CastSurvivalInstinctsAction : public CastBuffSpellAction
{
public:
    CastSurvivalInstinctsAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "survival instincts") {}
};

class CastFrenziedRegenerationAction : public CastBuffSpellAction
{
public:
    CastFrenziedRegenerationAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "frenzied regeneration") {}
};

class CastThornsAction : public CastBuffSpellAction
{
public:
    CastThornsAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "thorns") {}
};

class CastThornsOnPartyAction : public BuffOnPartyAction
{
public:
    CastThornsOnPartyAction(PlayerbotAI* botAI) : BuffOnPartyAction(botAI, "thorns") {}
};

class CastThornsOnMainTankAction : public BuffOnMainTankAction
{
public:
    CastThornsOnMainTankAction(PlayerbotAI* botAI) : BuffOnMainTankAction(botAI, "thorns", false) {}
};

class CastOmenOfClarityAction : public CastBuffSpellAction
{
public:
    CastOmenOfClarityAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "omen of clarity") {}
};

class CastWrathAction : public CastSpellAction
{
public:
    CastWrathAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "wrath") {}
};

class CastStarfallAction : public CastSpellAction
{
public:
    CastStarfallAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "starfall") {}
};

class CastHurricaneAction : public CastSpellAction
{
public:
    CastHurricaneAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "hurricane") {}
    ActionThreatType getThreatType() override { return ActionThreatType::Aoe; }
};

class CastMoonfireAction : public CastDebuffSpellAction
{
public:
    CastMoonfireAction(PlayerbotAI* botAI) : CastDebuffSpellAction(botAI, "moonfire", true) {}
};

class CastInsectSwarmAction : public CastDebuffSpellAction
{
public:
    CastInsectSwarmAction(PlayerbotAI* botAI) : CastDebuffSpellAction(botAI, "insect swarm", true) {}
};

class CastStarfireAction : public CastSpellAction
{
public:
    CastStarfireAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "starfire") {}
};

class CastEntanglingRootsAction : public CastSpellAction
{
public:
    CastEntanglingRootsAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "entangling roots") {}
};

class CastEntanglingRootsCcAction : public DruidCcAction
{
public:
    CastEntanglingRootsCcAction(PlayerbotAI* botAI)
        : DruidCcAction(botAI, "entangling roots", 339, "entangling roots on cc") {}
};

class CastHibernateAction : public CastSpellAction
{
public:
    CastHibernateAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "hibernate") {}
};

class CastHibernateCcAction : public DruidCcAction
{
public:
    CastHibernateCcAction(PlayerbotAI* botAI)
        : DruidCcAction(botAI, "hibernate", 2637, "hibernate on cc") {}
};

class CastNaturesGraspAction : public CastBuffSpellAction
{
public:
    CastNaturesGraspAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "nature's grasp") {}
};

class DruidDispelAction : public CurePartyMemberAction
{
public:
    DruidDispelAction(PlayerbotAI* ai, std::string const alias, uint32 dispelType, bool self = false)
        : CurePartyMemberAction(ai, "remove corruption", dispelType), alias(alias), self(self) {}
    std::string const getName() override { return alias; }
    Value<Unit*>* GetTargetValue() override;
    bool isUseful() override;
    bool isPossible() override;
    bool Execute(Event event) override;
    NextAction** getPrerequisites() override;

private:
    bool SelectSpell();
    std::string alias;
    bool self;
};

class CastCurePoisonAction : public DruidDispelAction
{
public:
    CastCurePoisonAction(PlayerbotAI* botAI) : DruidDispelAction(botAI, "cure poison", DISPEL_POISON, true) {}
};

class CastCurePoisonOnPartyAction : public DruidDispelAction
{
public:
    CastCurePoisonOnPartyAction(PlayerbotAI* botAI) : DruidDispelAction(botAI, "cure poison on party", DISPEL_POISON) {}
};

class CastAbolishPoisonAction : public DruidDispelAction
{
public:
    CastAbolishPoisonAction(PlayerbotAI* botAI) : DruidDispelAction(botAI, "abolish poison", DISPEL_POISON, true) {}
};

class CastAbolishPoisonOnPartyAction : public DruidDispelAction
{
public:
    CastAbolishPoisonOnPartyAction(PlayerbotAI* botAI) : DruidDispelAction(botAI, "abolish poison on party", DISPEL_POISON) {}
};

class CastBarkskinAction : public CastBuffSpellAction
{
public:
    CastBarkskinAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "barkskin") {}
};

class CastInnervateAction : public CastSpellAction
{
public:
    CastInnervateAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "innervate") {}

    std::string const GetTargetName() override { return "self target"; }
};

class CastTranquilityAction : public CastAoeHealSpellAction
{
public:
    CastTranquilityAction(PlayerbotAI* botAI)
        : CastAoeHealSpellAction(botAI, "tranquility", 15.0f, HealingManaEfficiency::MEDIUM)
    {
    }
};

class CastNaturesSwiftnessAction : public CastBuffSpellAction
{
public:
    CastNaturesSwiftnessAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "nature's swiftness") {}
};

class CastWildGrowthOnPartyAction : public HealPartyMemberAction
{
public:
    CastWildGrowthOnPartyAction(PlayerbotAI* ai)
        : HealPartyMemberAction(ai, "wild growth", 15.0f, HealingManaEfficiency::VERY_HIGH)
    {
    }
};

class CastPartySwiftmendAction : public HealPartyMemberAction
{
public:
    CastPartySwiftmendAction(PlayerbotAI* ai)
        : HealPartyMemberAction(ai, "swiftmend", 15.0f, HealingManaEfficiency::MEDIUM)
    {
    }
};

class CastPartyNourishAction : public HealPartyMemberAction
{
public:
    CastPartyNourishAction(PlayerbotAI* ai) : HealPartyMemberAction(ai, "nourish", 25.0f, HealingManaEfficiency::LOW) {}
};

class CastDruidRemoveCurseOnPartyAction : public DruidDispelAction
{
public:
    CastDruidRemoveCurseOnPartyAction(PlayerbotAI* ai) : DruidDispelAction(ai, "remove curse on party", DISPEL_CURSE) {}
};

class CastInsectSwarmOnAttackerAction : public CastDebuffSpellOnAttackerAction
{
public:
    CastInsectSwarmOnAttackerAction(PlayerbotAI* ai) : CastDebuffSpellOnAttackerAction(ai, "insect swarm") {}
};

class CastMoonfireOnAttackerAction : public CastDebuffSpellOnAttackerAction
{
public:
    CastMoonfireOnAttackerAction(PlayerbotAI* ai) : CastDebuffSpellOnAttackerAction(ai, "moonfire") {}
};

class CastEnrageAction : public CastBuffSpellAction
{
public:
    CastEnrageAction(PlayerbotAI* ai) : CastBuffSpellAction(ai, "enrage") {}
};


class CastRejuvenationOnNotFullAction : public HealPartyMemberAction
{
public:
    CastRejuvenationOnNotFullAction(PlayerbotAI* ai)
        : HealPartyMemberAction(ai, "rejuvenation", 5.0f, HealingManaEfficiency::VERY_HIGH)
    {
    }
    bool isUseful() override;
    Unit* GetTarget() override;
    std::string const getName() override { return "rejuvenation on not full"; }
    bool Execute(Event event) override;
};

class CastForceOfNatureAction : public CastSpellAction
{
public:
    CastForceOfNatureAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "force of nature") {}
};

#endif
