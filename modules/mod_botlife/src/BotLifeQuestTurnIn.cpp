#include "BotLifeQuestTurnIn.h"
#include "BotLifeQuestData.h"

#include "Creature.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"

namespace BotLife
{
char const* QuestExecutionRejection(Player& bot, QuestPlanData const& data)
{
    if (data.error != QuestPlanReason::None)
        return ToString(data.error);
    QuestPlayerSnapshot const player = ReadQuestPlayer(data, bot);
    if (!player.validContext)
        return "invalid-context";
    if (player.eligibility != QuestPlanReason::None)
        return ToString(player.eligibility);
    Quest const* quest = sObjectMgr->GetQuestTemplate(data.questId);
    if (!quest || sObjectMgr->IsBrokenQuest(data.questId))
        return "missing-or-broken-quest";
    if (bot.GetGroup() || quest->HasFlag(QUEST_FLAGS_PARTY_ACCEPT))
        return "group-quest-unsupported";
    // Reward-choice policy and package rewards require a separate implementation.
    if (quest->GetRewChoiceItemsCount() || quest->GetQuestPackageID())
        return "reward-choice-unsupported";
    if (player.progress == QuestProgress::Failed)
        return "failed-quest";
    return nullptr;
}

bool TryTurnInQuest(Player& bot, QuestPlanData const& data, QuestSpawn const& ender, char const*& reason)
{
    reason = QuestExecutionRejection(bot, data);
    if (reason)
        return false;
    reason = "quest-not-complete-or-already-rewarded";
    if (bot.GetQuestStatus(data.questId) != QUEST_STATUS_COMPLETE || bot.GetQuestRewardStatus(data.questId))
        return false;
    reason = "interaction-blocked";
    if (bot.IsInCombat() || bot.HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) ||
        bot.IsNonMeleeSpellCasted(false))
        return false;
    reason = "ender-context-changed";
    if (ender.mapId != bot.GetMapId() || !(ender.phaseMask & bot.GetPhaseMask()))
        return false;
    Creature* npc = bot.GetMap()->GetCreatureBySpawnId(ender.guid);
    reason = "ender-missing-or-unavailable";
    if (!npc || !npc->IsInWorld() || !npc->IsAlive() || npc->IsInCombat() || npc->GetEntry() != ender.entry ||
        npc->GetMap() != bot.GetMap() || !(npc->GetPhaseMask() & bot.GetPhaseMask()) || !bot.CanSeeOrDetect(npc))
        return false;
    reason = "ender-interaction-denied";
    if (!npc->hasInvolvedQuest(data.questId) || !bot.CanInteractWithQuestGiver(npc) || !bot.IsWithinLOSInMap(npc))
        return false;
    Quest const* quest = sObjectMgr->GetQuestTemplate(data.questId);
    reason = "native-reward-denied";
    // The reward-ID overload checks inventory only in this core. Both checks are required.
    if (!quest || !bot.CanRewardQuest(quest, false) || !bot.CanRewardQuest(quest, uint32(0), false))
        return false;
    bot.RewardQuest(quest, 0, npc); // Native money/XP/items/reputation, persistence and script hooks.
    // No live pointer is dereferenced after hooks.
    reason = "reward-not-confirmed";
    if (!bot.GetQuestRewardStatus(data.questId) || bot.FindQuestSlot(data.questId) < MAX_QUEST_LOG_SIZE)
        return false;
    reason = "rewarded";
    return true;
}
}
