#ifndef PLAYERBOT_SHAMAN_WEAPON_IMBUE_H
#define PLAYERBOT_SHAMAN_WEAPON_IMBUE_H

#include "Unit.h"

class Item;
class Player;

// Only an equipped, usable, currently unenchanted weapon. Never replace poisons,
// another imbue, a trading partner's item, or an enchant that has not expired.
Item* GetShamanImbueWeapon(Player& bot, WeaponAttackType hand);

#endif
