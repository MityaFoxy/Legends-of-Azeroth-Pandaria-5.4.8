#include "BotLifeQuestInteraction.h"
#include "BotLifeQuestData.h"

#include "Creature.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"

namespace BotLife
{
char const* QuestAcquireRejection(Player& bot, QuestPlanData const& data)
{
    if (data.error != QuestPlanReason::None)
        return ToString(data.error);
    QuestPlayerSnapshot const snapshot = ReadQuestPlayer(data, bot);
    if (!snapshot.validContext)
        return "invalid-context";
    if (snapshot.eligibility != QuestPlanReason::None)
        return ToString(snapshot.eligibility);
    if (snapshot.progress != QuestProgress::NotTaken)
        return "already-taken-or-finished";
    Quest const* quest = sObjectMgr->GetQuestTemplate(data.questId);
    if (!quest)
        return "missing-quest";
    // AddQuestAndCheckCompletion has a native broken-quest auto-completion path.
    // Do not let a navigation/acceptance test accidentally exercise that shortcut.
    if (sObjectMgr->IsBrokenQuest(data.questId))
        return "broken-quest";
    if (bot.GetGroup() || quest->HasFlag(QUEST_FLAGS_PARTY_ACCEPT))
        return "group-quest-unsupported";
    return nullptr;
}

bool TryAcceptQuest(Player& bot, QuestPlanData const& data, QuestSpawn const& giver, char const*& reason)
{
    reason = QuestAcquireRejection(bot, data);
    if (reason)
        return false;
    reason = "interaction-blocked";
    if (bot.IsInCombat() || bot.HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) ||
        bot.IsNonMeleeSpellCasted(false))
        return false;
    reason = "giver-context-changed";
    if (giver.mapId != bot.GetMapId() || !(giver.phaseMask & bot.GetPhaseMask()))
        return false;
    // This store belongs to the bot's current map; no global object lookup/load.
    Creature* npc = bot.GetMap()->GetCreatureBySpawnId(giver.guid);
    reason = "giver-missing-or-unavailable";
    if (!npc || !npc->IsInWorld() || !npc->IsAlive() || npc->IsInCombat() ||
        npc->GetEntry() != giver.entry || npc->GetMap() != bot.GetMap() ||
        !(npc->GetPhaseMask() & bot.GetPhaseMask()) || !bot.CanSeeOrDetect(npc))
        return false;
    reason = "giver-no-longer-offers-quest";
    if (!npc->hasQuest(data.questId))
        return false;
    reason = "giver-interaction-denied";
    if (!bot.CanInteractWithQuestGiver(npc) || !bot.IsWithinLOSInMap(npc))
        return false;
    Quest const* quest = sObjectMgr->GetQuestTemplate(data.questId);
    reason = "native-acceptance-denied";
    if (!quest || !bot.CanTakeQuest(quest, false) || !bot.CanAddQuest(quest, false))
        return false;
    bot.AddQuestAndCheckCompletion(quest, npc);
    // Native hooks may change state; do not dereference npc/quest after the call.
    reason = "acceptance-not-confirmed";
    if (bot.FindQuestSlot(data.questId) >= MAX_QUEST_LOG_SIZE ||
        (bot.GetQuestStatus(data.questId) != QUEST_STATUS_INCOMPLETE &&
         bot.GetQuestStatus(data.questId) != QUEST_STATUS_COMPLETE))
        return false;
    reason = "accepted";
    return true;
}
}
