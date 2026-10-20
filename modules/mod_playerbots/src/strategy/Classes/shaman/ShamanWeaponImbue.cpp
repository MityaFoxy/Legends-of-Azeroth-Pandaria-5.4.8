#include "ShamanWeaponImbue.h"
#include "Item.h"
#include "Player.h"

Item* GetShamanImbueWeapon(Player& bot, WeaponAttackType hand)
{
    if ((hand != BASE_ATTACK && hand != OFF_ATTACK) ||
        bot.GetClass() != CLASS_SHAMAN || !bot.IsAlive() || bot.GetTradeData() ||
        !bot.CanUseAttackType(hand) || (hand == OFF_ATTACK && !bot.CanDualWield()))
        return nullptr;
    Item* item = bot.GetWeaponForAttack(hand, true);
    return item && !item->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) ? item : nullptr;
}
