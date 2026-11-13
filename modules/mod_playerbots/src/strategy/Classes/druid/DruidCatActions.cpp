#include "DruidCatActions.h"

#include "Playerbots.h"

bool CastTigersFuryAction::isUseful()
{
    // Native spell_dru_cat_form_check / spell_dru_tigers_fury reject these states.
    // Keep the existing default action, but spend its energy gain when useful.
    return bot->GetShapeshiftForm() == FORM_CAT && bot->GetPower(POWER_ENERGY) < 35 &&
        !bot->HasAura(106951) && CastBuffSpellAction::isUseful();
}
