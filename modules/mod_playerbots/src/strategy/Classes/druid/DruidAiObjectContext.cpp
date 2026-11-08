/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "DruidAiObjectContext.h"

#include "BearTankDruidStrategy.h"
#include "CasterDruidStrategy.h"
#include "CatDpsDruidStrategy.h"
#include "DruidActions.h"
#include "DruidBearActions.h"
#include "DruidCatActions.h"
#include "DruidShapeshiftActions.h"
#include "DruidTriggers.h"
#include "DruidValues.h"
#include "GenericDruidNonCombatStrategy.h"
#include "GenericDruidStrategy.h"
#include "HealDruidStrategy.h"
#include "MeleeDruidStrategy.h"
#include "Playerbots.h"

class DruidStrategyFactoryInternal : public NamedObjectContext<Strategy>
{
public:
    DruidStrategyFactoryInternal()
    {
        creators["nc"] = &DruidStrategyFactoryInternal::nc;
        creators["cat aoe"] = &DruidStrategyFactoryInternal::cat_aoe;
        creators["caster aoe"] = &DruidStrategyFactoryInternal::caster_aoe;
        creators["caster debuff"] = &DruidStrategyFactoryInternal::caster_debuff;
        creators["dps debuff"] = &DruidStrategyFactoryInternal::caster_debuff;
        creators["cure"] = &DruidStrategyFactoryInternal::cure;
        creators["melee"] = &DruidStrategyFactoryInternal::melee;
        creators["buff"] = &DruidStrategyFactoryInternal::buff;
        creators["boost"] = &DruidStrategyFactoryInternal::boost;
        creators["cc"] = &DruidStrategyFactoryInternal::cc;
        creators["healer dps"] = &DruidStrategyFactoryInternal::healer_dps;
    }

private:
    static Strategy* nc(PlayerbotAI* botAI) { return new GenericDruidNonCombatStrategy(botAI); }
    static Strategy* cat_aoe(PlayerbotAI* botAI) { return new CatAoeDruidStrategy(botAI); }
    static Strategy* caster_aoe(PlayerbotAI* botAI) { return new CasterDruidAoeStrategy(botAI); }
    static Strategy* caster_debuff(PlayerbotAI* botAI) { return new CasterDruidDebuffStrategy(botAI); }
    static Strategy* cure(PlayerbotAI* botAI) { return new DruidCureStrategy(botAI); }
    static Strategy* melee(PlayerbotAI* botAI) { return new MeleeDruidStrategy(botAI); }
    static Strategy* buff(PlayerbotAI* botAI) { return new GenericDruidBuffStrategy(botAI); }
    static Strategy* boost(PlayerbotAI* botAI) { return new DruidBoostStrategy(botAI); }
    static Strategy* cc(PlayerbotAI* botAI) { return new DruidCcStrategy(botAI); }
    static Strategy* healer_dps(PlayerbotAI* botAI) { return new DruidHealerDpsStrategy(botAI); }
};

class DruidDruidStrategyFactoryInternal : public NamedObjectContext<Strategy>
{
public:
    DruidDruidStrategyFactoryInternal() : NamedObjectContext<Strategy>(false, true)
    {
        creators["bear"] = &DruidDruidStrategyFactoryInternal::bear;
        creators["tank"] = &DruidDruidStrategyFactoryInternal::bear;
        creators["cat"] = &DruidDruidStrategyFactoryInternal::cat;
        creators["caster"] = &DruidDruidStrategyFactoryInternal::caster;
        creators["dps"] = &DruidDruidStrategyFactoryInternal::cat;
        creators["heal"] = &DruidDruidStrategyFactoryInternal::heal;
    }

private:
    static Strategy* bear(PlayerbotAI* botAI) { return new BearTankDruidStrategy(botAI); }
    static Strategy* cat(PlayerbotAI* botAI) { return new CatDpsDruidStrategy(botAI); }
    static Strategy* caster(PlayerbotAI* botAI) { return new CasterDruidStrategy(botAI); }
    static Strategy* heal(PlayerbotAI* botAI) { return new HealDruidStrategy(botAI); }
};

class DruidValueFactoryInternal : public NamedObjectContext<UntypedValue>
{
public:
    DruidValueFactoryInternal()
    {
        creators["mark of the wild target"] = &DruidValueFactoryInternal::mark_target;
    }

private:
    static UntypedValue* mark_target(PlayerbotAI* ai) { return new DruidMarkOfTheWildTargetValue(ai); }
};

class DruidTriggerFactoryInternal : public NamedObjectContext<Trigger>
{
public:
    DruidTriggerFactoryInternal()
    {
        creators["cat form"] = &DruidTriggerFactoryInternal::cat_form;
        creators["bear form"] = &DruidTriggerFactoryInternal::bear_form;
        creators["combo points not full"] = &DruidTriggerFactoryInternal::combo_not_full;
        creators["combo points not full and high energy"] = &DruidTriggerFactoryInternal::combo_energy;
        creators["combo points available"] = &DruidTriggerFactoryInternal::combo_finisher;
        creators["ferocious bite time"] = &DruidTriggerFactoryInternal::bite;
        creators["target with combo points almost dead"] = &DruidTriggerFactoryInternal::dying;
        creators["savage roar"] = &DruidTriggerFactoryInternal::savage_roar;
        creators["rake"] = &DruidTriggerFactoryInternal::rake;
        creators["moonfire"] = &DruidTriggerFactoryInternal::moonfire;
        creators["faerie fire"] = &DruidTriggerFactoryInternal::faerie_fire;
        creators["faerie fire (feral)"] = &DruidTriggerFactoryInternal::faerie_fire;
        creators["mark of the wild"] = &DruidTriggerFactoryInternal::mark;
        creators["mark of the wild on party"] = &DruidTriggerFactoryInternal::mark_party;
        creators["berserk"] = &DruidTriggerFactoryInternal::berserk;
        creators["eclipse (lunar)"] = &DruidTriggerFactoryInternal::lunar;
        creators["eclipse (solar)"] = &DruidTriggerFactoryInternal::solar;
        creators["eclipse (lunar) cooldown"] = &DruidTriggerFactoryInternal::lunar_direction;
        creators["eclipse (solar) cooldown"] = &DruidTriggerFactoryInternal::solar_direction;
        creators["party member cure poison"] = &DruidTriggerFactoryInternal::cure_poison;
        creators["party member remove curse"] = &DruidTriggerFactoryInternal::remove_curse;
        creators["party member cure magic"] = &DruidTriggerFactoryInternal::cure_magic;
    }

private:
    static Trigger* cat_form(PlayerbotAI* ai) { return new DruidFormTrigger(ai, "cat form", 768, FORM_CAT); }
    static Trigger* cure_poison(PlayerbotAI* ai) { return new DruidDispelTrigger(ai, "party member cure poison", DISPEL_POISON); }
    static Trigger* remove_curse(PlayerbotAI* ai) { return new DruidDispelTrigger(ai, "party member remove curse", DISPEL_CURSE); }
    static Trigger* cure_magic(PlayerbotAI* ai) { return new DruidDispelTrigger(ai, "party member cure magic", DISPEL_MAGIC); }
    static Trigger* bear_form(PlayerbotAI* ai) { return new DruidFormTrigger(ai, "bear form", 5487, FORM_BEAR); }
    static Trigger* combo_not_full(PlayerbotAI* ai) { return new DruidComboPointsTrigger(ai, "combo points not full", DruidComboPointsTrigger::Condition::NotFull); }
    static Trigger* combo_energy(PlayerbotAI* ai) { return new DruidComboPointsTrigger(ai, "combo points not full and high energy", DruidComboPointsTrigger::Condition::NotFullHighEnergy); }
    static Trigger* combo_finisher(PlayerbotAI* ai) { return new DruidComboPointsTrigger(ai, "combo points available", DruidComboPointsTrigger::Condition::Finisher); }
    static Trigger* bite(PlayerbotAI* ai) { return new DruidComboPointsTrigger(ai, "ferocious bite time", DruidComboPointsTrigger::Condition::Finisher); }
    static Trigger* dying(PlayerbotAI* ai) { return new DruidComboPointsTrigger(ai, "target with combo points almost dead", DruidComboPointsTrigger::Condition::DyingTarget); }
    static Trigger* savage_roar(PlayerbotAI* ai) { return new DruidSavageRoarTrigger(ai); }
    static Trigger* rake(PlayerbotAI* ai) { return new DruidDebuffTrigger(ai, "rake", 1822, true, 6.0f, true); }
    static Trigger* moonfire(PlayerbotAI* ai) { return new DruidDebuffTrigger(ai, "moonfire", 8921, true); }
    static Trigger* faerie_fire(PlayerbotAI* ai) { return new DruidDebuffTrigger(ai, "faerie fire", 770); }
    static Trigger* mark(PlayerbotAI* ai) { return new DruidMarkOfTheWildTrigger(ai); }
    static Trigger* mark_party(PlayerbotAI* ai) { return new DruidMarkOfTheWildTrigger(ai, true); }
    static Trigger* berserk(PlayerbotAI* ai) { return new DruidBerserkTrigger(ai); }
    static Trigger* lunar(PlayerbotAI* ai) { return new DruidEclipseTrigger(ai, "eclipse (lunar)", true, false); }
    static Trigger* solar(PlayerbotAI* ai) { return new DruidEclipseTrigger(ai, "eclipse (solar)", false, false); }
    static Trigger* lunar_direction(PlayerbotAI* ai) { return new DruidEclipseTrigger(ai, "eclipse (lunar) cooldown", true, true); }
    static Trigger* solar_direction(PlayerbotAI* ai) { return new DruidEclipseTrigger(ai, "eclipse (solar) cooldown", false, true); }
};

class DruidControlTriggerFactoryInternal : public NamedObjectContext<Trigger>
{
public:
    DruidControlTriggerFactoryInternal()
    {
        creators["entangling roots"] = &roots;
        creators["hibernate"] = &hibernate;
        creators["bash"] = &bash;
        creators["bash on enemy healer"] = &bash_healer;
        creators["nature's swiftness"] = &swiftness;
    }

private:
    static Trigger* roots(PlayerbotAI* ai) { return new DruidControlTrigger(ai, "entangling roots", "entangling roots on cc"); }
    static Trigger* hibernate(PlayerbotAI* ai) { return new DruidControlTrigger(ai, "hibernate", "hibernate on cc"); }
    static Trigger* bash(PlayerbotAI* ai) { return new DruidControlTrigger(ai, "bash", "bash"); }
    static Trigger* bash_healer(PlayerbotAI* ai) { return new DruidControlTrigger(ai, "bash on enemy healer", "bash on enemy healer"); }
    static Trigger* swiftness(PlayerbotAI* ai) { return new DruidNaturesSwiftnessTrigger(ai); }
};

class DruidAiObjectContextInternal : public NamedObjectContext<Action>
{
public:
    DruidAiObjectContextInternal()
    {
        creators["feral charge - bear"] = &DruidAiObjectContextInternal::feral_charge_bear;
        creators["feral charge - cat"] = &DruidAiObjectContextInternal::feral_charge_cat;
        creators["swipe (bear)"] = &DruidAiObjectContextInternal::swipe_bear;
        creators["faerie fire (feral)"] = &DruidAiObjectContextInternal::faerie_fire_feral;
        creators["faerie fire"] = &DruidAiObjectContextInternal::faerie_fire;
        creators["bear form"] = &DruidAiObjectContextInternal::bear_form;
        creators["dire bear form"] = &DruidAiObjectContextInternal::dire_bear_form;
        creators["moonkin form"] = &DruidAiObjectContextInternal::moonkin_form;
        creators["cat form"] = &DruidAiObjectContextInternal::cat_form;
        creators["tree form"] = &DruidAiObjectContextInternal::tree_form;
        creators["travel form"] = &DruidAiObjectContextInternal::travel_form;
        creators["aquatic form"] = &DruidAiObjectContextInternal::aquatic_form;
        creators["caster form"] = &DruidAiObjectContextInternal::caster_form;
        creators["cancel tree form"] = &DruidAiObjectContextInternal::cancel_tree_form;
        creators["mangle (bear)"] = &DruidAiObjectContextInternal::mangle_bear;
        creators["maul"] = &DruidAiObjectContextInternal::maul;
        creators["bash"] = &DruidAiObjectContextInternal::bash;
        creators["swipe"] = &DruidAiObjectContextInternal::swipe;
        creators["growl"] = &DruidAiObjectContextInternal::growl;
        creators["demoralizing roar"] = &DruidAiObjectContextInternal::demoralizing_roar;
        creators["hibernate"] = &DruidAiObjectContextInternal::hibernate;
        creators["entangling roots"] = &DruidAiObjectContextInternal::entangling_roots;
        creators["entangling roots on cc"] = &DruidAiObjectContextInternal::entangling_roots_on_cc;
        creators["hibernate"] = &DruidAiObjectContextInternal::hibernate;
        creators["hibernate on cc"] = &DruidAiObjectContextInternal::hibernate_on_cc;
        creators["wrath"] = &DruidAiObjectContextInternal::wrath;
        creators["starfall"] = &DruidAiObjectContextInternal::starfall;
        creators["insect swarm"] = &DruidAiObjectContextInternal::insect_swarm;
        creators["moonfire"] = &DruidAiObjectContextInternal::moonfire;
        creators["starfire"] = &DruidAiObjectContextInternal::starfire;
        creators["nature's grasp"] = &DruidAiObjectContextInternal::natures_grasp;
        creators["claw"] = &DruidAiObjectContextInternal::claw;
        creators["mangle (cat)"] = &DruidAiObjectContextInternal::mangle_cat;
        creators["swipe (cat)"] = &DruidAiObjectContextInternal::swipe_cat;
        creators["rake"] = &DruidAiObjectContextInternal::rake;
        creators["rake on attacker"] = &DruidAiObjectContextInternal::rake_on_attacker;
        creators["ferocious bite"] = &DruidAiObjectContextInternal::ferocious_bite;
        creators["rip"] = &DruidAiObjectContextInternal::rip;
        creators["cower"] = &DruidAiObjectContextInternal::cower;
        creators["survival instincts"] = &DruidAiObjectContextInternal::survival_instincts;
        creators["frenzied regeneration"] = &DruidAiObjectContextInternal::frenzied_regeneration;
        creators["thorns"] = &DruidAiObjectContextInternal::thorns;
        creators["thorns on party"] = &DruidAiObjectContextInternal::thorns_on_party;
        creators["thorns on main tank"] = &DruidAiObjectContextInternal::thorns_on_main_tank;
        creators["cure poison"] = &DruidAiObjectContextInternal::cure_poison;
        creators["cure poison on party"] = &DruidAiObjectContextInternal::cure_poison_on_party;
        creators["abolish poison"] = &DruidAiObjectContextInternal::abolish_poison;
        creators["abolish poison on party"] = &DruidAiObjectContextInternal::abolish_poison_on_party;
        creators["berserk"] = &DruidAiObjectContextInternal::berserk;
        creators["tiger's fury"] = &DruidAiObjectContextInternal::tigers_fury;
        creators["savage roar"] = &DruidAiObjectContextInternal::savage_roar;
        creators["mark of the wild"] = &DruidAiObjectContextInternal::mark_of_the_wild;
        creators["mark of the wild on party"] = &DruidAiObjectContextInternal::mark_of_the_wild_on_party;
        creators["regrowth"] = &DruidAiObjectContextInternal::regrowth;
        creators["rejuvenation"] = &DruidAiObjectContextInternal::rejuvenation;
        creators["healing touch"] = &DruidAiObjectContextInternal::healing_touch;
        creators["regrowth on party"] = &DruidAiObjectContextInternal::regrowth_on_party;
        creators["rejuvenation on party"] = &DruidAiObjectContextInternal::rejuvenation_on_party;
        creators["rejuvenation on not full"] = &DruidAiObjectContextInternal::rejuvenation_on_not_full;
        creators["healing touch on party"] = &DruidAiObjectContextInternal::healing_touch_on_party;
        creators["rebirth"] = &DruidAiObjectContextInternal::rebirth;
        creators["revive"] = &DruidAiObjectContextInternal::revive;
        creators["barkskin"] = &DruidAiObjectContextInternal::barkskin;
        creators["lacerate"] = &DruidAiObjectContextInternal::lacerate;
        creators["hurricane"] = &DruidAiObjectContextInternal::hurricane;
        creators["innervate"] = &DruidAiObjectContextInternal::innervate;
        creators["tranquility"] = &DruidAiObjectContextInternal::tranquility;
        creators["bash on enemy healer"] = &DruidAiObjectContextInternal::bash_on_enemy_healer;
        creators["omen of clarity"] = &DruidAiObjectContextInternal::omen_of_clarity;
        creators["nature's swiftness"] = &DruidAiObjectContextInternal::natures_swiftness;
        creators["prowl"] = &DruidAiObjectContextInternal::prowl;
        creators["dash"] = &DruidAiObjectContextInternal::dash;
        creators["shred"] = &DruidAiObjectContextInternal::shred;
        creators["ravage"] = &DruidAiObjectContextInternal::ravage;
        creators["pounce"] = &DruidAiObjectContextInternal::pounce;
        creators["wild growth on party"] = &DruidAiObjectContextInternal::wild_growth_on_party;
        creators["swiftmend on party"] = &DruidAiObjectContextInternal::swiftmend_on_party;
        creators["nourish on party"] = &DruidAiObjectContextInternal::nourish_on_party;
        creators["remove curse on party"] = &DruidAiObjectContextInternal::remove_curse_on_party;
        creators["nature's cure on party"] = &DruidAiObjectContextInternal::cure_magic_on_party;
        creators["insect swarm on attacker"] = &DruidAiObjectContextInternal::insect_swarm_on_attacker;
        creators["moonfire on attacker"] = &DruidAiObjectContextInternal::moonfire_on_attacker;
        creators["enrage"] = &DruidAiObjectContextInternal::enrage;
        creators["force of nature"] = &DruidAiObjectContextInternal::force_of_nature;
    }

private:
    static Action* natures_swiftness(PlayerbotAI* botAI) { return new CastNaturesSwiftnessAction(botAI); }
    static Action* omen_of_clarity(PlayerbotAI* botAI) { return new CastOmenOfClarityAction(botAI); }
    static Action* tranquility(PlayerbotAI* botAI) { return new CastTranquilityAction(botAI); }
    static Action* feral_charge_bear(PlayerbotAI* botAI) { return new CastFeralChargeBearAction(botAI); }
    static Action* feral_charge_cat(PlayerbotAI* botAI) { return new CastFeralChargeCatAction(botAI); }
    static Action* swipe_bear(PlayerbotAI* botAI) { return new CastSwipeBearAction(botAI); }
    static Action* faerie_fire_feral(PlayerbotAI* botAI) { return new CastFaerieFireFeralAction(botAI); }
    static Action* faerie_fire(PlayerbotAI* botAI) { return new CastFaerieFireAction(botAI); }
    static Action* bear_form(PlayerbotAI* botAI) { return new CastBearFormAction(botAI); }
    static Action* dire_bear_form(PlayerbotAI* botAI) { return new CastDireBearFormAction(botAI); }
    static Action* cat_form(PlayerbotAI* botAI) { return new CastCatFormAction(botAI); }
    static Action* tree_form(PlayerbotAI* botAI) { return new CastTreeFormAction(botAI); }
    static Action* travel_form(PlayerbotAI* botAI) { return new CastTravelFormAction(botAI); }
    static Action* aquatic_form(PlayerbotAI* botAI) { return new CastAquaticFormAction(botAI); }
    static Action* caster_form(PlayerbotAI* botAI) { return new CastCasterFormAction(botAI); }
    static Action* cancel_tree_form(PlayerbotAI* botAI) { return new CastCancelTreeFormAction(botAI); }
    static Action* mangle_bear(PlayerbotAI* botAI) { return new CastMangleBearAction(botAI); }
    static Action* maul(PlayerbotAI* botAI) { return new CastMaulAction(botAI); }
    static Action* bash(PlayerbotAI* botAI) { return new CastBashAction(botAI); }
    static Action* swipe(PlayerbotAI* botAI) { return new CastSwipeAction(botAI); }
    static Action* growl(PlayerbotAI* botAI) { return new CastGrowlAction(botAI); }
    static Action* demoralizing_roar(PlayerbotAI* botAI) { return new CastDemoralizingRoarAction(botAI); }
    static Action* moonkin_form(PlayerbotAI* botAI) { return new CastMoonkinFormAction(botAI); }
    static Action* hibernate(PlayerbotAI* botAI) { return new CastHibernateAction(botAI); }
    static Action* entangling_roots(PlayerbotAI* botAI) { return new CastEntanglingRootsAction(botAI); }
    static Action* hibernate_on_cc(PlayerbotAI* botAI) { return new CastHibernateCcAction(botAI); }
    static Action* entangling_roots_on_cc(PlayerbotAI* botAI) { return new CastEntanglingRootsCcAction(botAI); }
    static Action* wrath(PlayerbotAI* botAI) { return new CastWrathAction(botAI); }
    static Action* starfall(PlayerbotAI* botAI) { return new CastStarfallAction(botAI); }
    static Action* insect_swarm(PlayerbotAI* botAI) { return new CastInsectSwarmAction(botAI); }
    static Action* moonfire(PlayerbotAI* botAI) { return new CastMoonfireAction(botAI); }
    static Action* starfire(PlayerbotAI* botAI) { return new CastStarfireAction(botAI); }
    static Action* natures_grasp(PlayerbotAI* botAI) { return new CastNaturesGraspAction(botAI); }
    static Action* claw(PlayerbotAI* botAI) { return new CastClawAction(botAI); }
    static Action* mangle_cat(PlayerbotAI* botAI) { return new CastMangleCatAction(botAI); }
    static Action* swipe_cat(PlayerbotAI* botAI) { return new CastSwipeCatAction(botAI); }
    static Action* rake(PlayerbotAI* botAI) { return new CastRakeAction(botAI); }
    static Action* rake_on_attacker(PlayerbotAI* botAI) { return new CastRakeOnMeleeAttackersAction(botAI); }
    static Action* ferocious_bite(PlayerbotAI* botAI) { return new CastFerociousBiteAction(botAI); }
    static Action* rip(PlayerbotAI* botAI) { return new CastRipAction(botAI); }
    static Action* cower(PlayerbotAI* botAI) { return new CastCowerAction(botAI); }
    static Action* survival_instincts(PlayerbotAI* botAI) { return new CastSurvivalInstinctsAction(botAI); }
    static Action* frenzied_regeneration(PlayerbotAI* botAI) { return new CastFrenziedRegenerationAction(botAI); }
    static Action* thorns(PlayerbotAI* botAI) { return new CastThornsAction(botAI); }
    static Action* thorns_on_party(PlayerbotAI* botAI) { return new CastThornsOnPartyAction(botAI); }
    static Action* thorns_on_main_tank(PlayerbotAI* botAI) { return new CastThornsOnMainTankAction(botAI); }
    static Action* cure_poison(PlayerbotAI* botAI) { return new CastCurePoisonAction(botAI); }
    static Action* cure_poison_on_party(PlayerbotAI* botAI) { return new CastCurePoisonOnPartyAction(botAI); }
    static Action* abolish_poison(PlayerbotAI* botAI) { return new CastAbolishPoisonAction(botAI); }
    static Action* abolish_poison_on_party(PlayerbotAI* botAI) { return new CastAbolishPoisonOnPartyAction(botAI); }
    static Action* berserk(PlayerbotAI* botAI) { return new CastBerserkAction(botAI); }
    static Action* tigers_fury(PlayerbotAI* botAI) { return new CastTigersFuryAction(botAI); }
    static Action* savage_roar(PlayerbotAI* botAI) { return new CastSavageRoarAction(botAI); }
    static Action* mark_of_the_wild(PlayerbotAI* botAI) { return new CastMarkOfTheWildAction(botAI); }
    static Action* mark_of_the_wild_on_party(PlayerbotAI* botAI) { return new CastMarkOfTheWildOnPartyAction(botAI); }
    static Action* regrowth(PlayerbotAI* botAI) { return new CastRegrowthAction(botAI); }
    static Action* rejuvenation(PlayerbotAI* botAI) { return new CastRejuvenationAction(botAI); }
    static Action* healing_touch(PlayerbotAI* botAI) { return new CastHealingTouchAction(botAI); }
    static Action* regrowth_on_party(PlayerbotAI* botAI) { return new CastRegrowthOnPartyAction(botAI); }
    static Action* rejuvenation_on_party(PlayerbotAI* botAI) { return new CastRejuvenationOnPartyAction(botAI); }
    static Action* rejuvenation_on_not_full(PlayerbotAI* botAI) { return new CastRejuvenationOnNotFullAction(botAI); }
    static Action* healing_touch_on_party(PlayerbotAI* botAI) { return new CastHealingTouchOnPartyAction(botAI); }
    static Action* rebirth(PlayerbotAI* botAI) { return new CastRebirthAction(botAI); }
    static Action* revive(PlayerbotAI* botAI) { return new CastReviveAction(botAI); }
    static Action* barkskin(PlayerbotAI* botAI) { return new CastBarkskinAction(botAI); }
    static Action* lacerate(PlayerbotAI* botAI) { return new CastLacerateAction(botAI); }
    static Action* hurricane(PlayerbotAI* botAI) { return new CastHurricaneAction(botAI); }
    static Action* innervate(PlayerbotAI* botAI) { return new CastInnervateAction(botAI); }
    static Action* bash_on_enemy_healer(PlayerbotAI* botAI) { return new CastBashOnEnemyHealerAction(botAI); }
    static Action* ravage(PlayerbotAI* botAI) { return new CastRavageAction(botAI); }
    static Action* pounce(PlayerbotAI* botAI) { return new CastPounceAction(botAI); }
    static Action* prowl(PlayerbotAI* botAI) { return new CastProwlAction(botAI); }
    static Action* dash(PlayerbotAI* botAI) { return new CastDashAction(botAI); }
    static Action* shred(PlayerbotAI* botAI) { return new CastShredAction(botAI); }
    static Action* wild_growth_on_party(PlayerbotAI* ai) { return new CastWildGrowthOnPartyAction(ai); }
    static Action* swiftmend_on_party(PlayerbotAI* ai) { return new CastPartySwiftmendAction(ai); }
    static Action* nourish_on_party(PlayerbotAI* ai) { return new CastPartyNourishAction(ai); }
    static Action* remove_curse_on_party(PlayerbotAI* ai) { return new CastDruidRemoveCurseOnPartyAction(ai); }
    static Action* cure_magic_on_party(PlayerbotAI* ai) { return new DruidDispelAction(ai, "nature's cure on party", DISPEL_MAGIC); }
    static Action* insect_swarm_on_attacker(PlayerbotAI* ai) { return new CastInsectSwarmOnAttackerAction(ai); }
    static Action* moonfire_on_attacker(PlayerbotAI* ai) { return new CastMoonfireOnAttackerAction(ai); }
    static Action* enrage(PlayerbotAI* ai) { return new CastEnrageAction(ai); }
    static Action* force_of_nature(PlayerbotAI* ai) { return new CastForceOfNatureAction(ai); }
};

DruidAiObjectContext::DruidAiObjectContext(PlayerbotAI* botAI) : AiObjectContext(botAI)
{
    strategyContexts.Add(new DruidStrategyFactoryInternal());
    strategyContexts.Add(new DruidDruidStrategyFactoryInternal());
    actionContexts.Add(new DruidAiObjectContextInternal());
    triggerContexts.Add(new DruidTriggerFactoryInternal());
    triggerContexts.Add(new DruidControlTriggerFactoryInternal());
    valueContexts.Add(new DruidValueFactoryInternal());
}
