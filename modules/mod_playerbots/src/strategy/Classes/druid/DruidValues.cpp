#include "DruidValues.h"

#include "Playerbots.h"

uint32 DruidDispelSpell(Player* bot, uint32 dispelType)
{
    // CastSpell rejects flight. In particular, do not enqueue caster-form
    // cancellation while airborne just to satisfy a dispel prerequisite.
    if (bot->IsFlying() || bot->IsInFlight())
        return 0;
    // SpecializationSpells.dbc: 2782 for 102/103/104, 88423 for 105.
    if (dispelType != DISPEL_POISON && dispelType != DISPEL_CURSE && dispelType != DISPEL_MAGIC)
        return 0;
    if (bot->GetTalentSpecialization() == SPEC_DRUID_RESTORATION)
        return bot->HasSpell(88423) ? 88423 : 0;
    if (dispelType == DISPEL_MAGIC)
        return 0;
    return bot->HasSpell(2782) ? 2782 : 0;
}

bool DruidNeedsDispel(PlayerbotAI* ai, Unit* target, uint32 dispelType)
{
    return target && target->IsInWorld() && target->IsAlive() && ai->GetBot()->IsFriendlyTo(target) &&
        ai->HasAuraToDispel(target, dispelType);
}

bool DruidNeedsMarkOfTheWild(PlayerbotAI* ai, Unit* target)
{
    // Match Spell::SelectImplicitRaidTargetsIfNeed (target type 118).
    // Selecting an unbuffed pet from another subgroup repeatedly casts the
    // raid buff without applying it to that pet. Keep searching for a player.
    return target && target->IsAlive() && !target->IsPetGuardianStuff() &&
        !ai->HasAnyAuraOf(target, "mark of the wild", "blessing of kings", "legacy of the emperor",
            "embrace of the shale spider", nullptr);
}

namespace
{
    class DruidMarkTargetPredicate : public FindPlayerPredicate
    {
    public:
        explicit DruidMarkTargetPredicate(PlayerbotAI* ai) : ai(ai) {}
        bool Check(Unit* target) override { return DruidNeedsMarkOfTheWild(ai, target); }

    private:
        PlayerbotAI* ai;
    };
}

Unit* DruidMarkOfTheWildTargetValue::Calculate()
{
    DruidMarkTargetPredicate predicate(botAI);
    return FindPartyMember(predicate);
}
