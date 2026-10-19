#ifndef _BOTLIFE_PROVISIONING_H
#define _BOTLIFE_PROVISIONING_H
class PlayerbotAI;
namespace BotLife
{
// Explicit administrator test bootstrap, never an ordinary activity/repair.
void LoadProvisioningConfig();
bool ProvisionMissingEquipment(PlayerbotAI& ai, char const*& reason);
}
#endif
