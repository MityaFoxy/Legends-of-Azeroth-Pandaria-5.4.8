#include "BotLifeQuestHunt.h"
#include "BotLifeReadiness.h"
#include "BotLifeCombatAssessment.h"

#include "Creature.h"
#include "Log.h"
#include "Map.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include <cmath>
#include <limits>
#include <cstring>

namespace BotLife
{
namespace
{
Creature* Resolve(Player& bot, QuestSpawn const& spawn)
{
    if (!bot.IsInWorld() || bot.IsDuringRemoveFromWorld() || spawn.mapId != bot.GetMapId())
        return nullptr;
    Creature* npc = bot.GetMap()->GetCreatureBySpawnId(spawn.guid);
    return npc && npc->IsInWorld() && npc->GetMap() == bot.GetMap() &&
        npc->GetEntry() == spawn.entry && (npc->GetPhaseMask() & bot.GetPhaseMask()) ? npc : nullptr;
}

bool Available(Player& bot, Creature& npc)
{
    return npc.IsAlive() && !npc.IsInCombat() && !npc.IsInEvadeMode() &&
        !npc.GetOwnerGUID() &&
        npc.GetLootRecipients().empty() && bot.IsValidAttackTarget(&npc) && bot.CanSeeOrDetect(&npc);
}
}

std::optional<QuestSpawn> QuestHunt::Choose(QuestPlanData const& data, QuestPlayerSnapshot const& player,
    std::unordered_set<uint32_t> const& visited, std::optional<QuestSpawn>* obstructed, uint32_t* blocker) const
{
    if (obstructed) obstructed->reset();
    if (blocker) *blocker = 0;
    double obstructionDistance = std::numeric_limits<double>::infinity();
    std::optional<QuestSpawn> best;
    double distance = std::numeric_limits<double>::infinity();
    for (QuestKillObjective const& objective : data.objectives)
    {
        auto const counter = player.counters.find(objective.id);
        if (counter != player.counters.end() && counter->second >= objective.amount)
            continue;
        for (QuestSpawn candidate : objective.candidates)
        {
            if (visited.count(candidate.guid) || candidate.mapId != player.mapId ||
                !(candidate.phaseMask & player.phaseMask))
                continue;
            // An unloaded grid is a travel candidate, never force-loaded or attacked remotely.
            Creature* npc = bot->GetMap()->GetCreatureBySpawnId(candidate.guid);
            if (npc)
            {
                if (Resolve(*bot, candidate) != npc || !Available(*bot, *npc))
                    continue;
                candidate.x = npc->GetPositionX();
                candidate.y = npc->GetPositionY();
                candidate.z = npc->GetPositionZ();
            }
            double const dx = double(candidate.x) - player.x, dy = double(candidate.y) - player.y,
                dz = double(candidate.z) - player.z;
            double const next = dx * dx + dy * dy + dz * dz;
            _safety.SetTarget(candidate.guid);
            if (!_safety.CanApproach(candidate))
            {
                if (obstructed && blocker && next < obstructionDistance && _safety.Blocker() &&
                    std::strcmp(_safety.Reason(), "hostile-on-route") == 0)
                {
                    *obstructed = candidate;
                    *blocker = _safety.Blocker();
                    obstructionDistance = next;
                }
                continue;
            }
            if (std::isfinite(next) && (next < distance ||
                (next == distance && best && candidate.guid < best->guid)))
            {
                best = candidate;
                distance = next;
            }
        }
    }
    _safety.SetTarget(best ? best->guid : 0);
    return best;
}

std::optional<QuestSpawn> QuestHunt::RouteObstacle(uint32_t spawn, bool allowDistant) const
{
    Creature* npc = bot->GetMap()->GetCreatureBySpawnId(spawn);
    if (!npc || !Available(*bot, *npc) || !npc->IsHostileTo(bot) ||
        !bot->IsWithinDistInMap(npc, allowDistant ? 90 : 60) || bot->IsMounted())
        return std::nullopt;
    QuestSpawn target{spawn, npc->GetEntry(), bot->GetMapId(), npc->GetPhaseMask(),
        npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()};
    if (Resolve(*bot, target) != npc)
        return std::nullopt;
    _safety.SetTarget(spawn);
    if (!_safety.CanApproach(target))
        return std::nullopt; // Includes neighbours/patrols; never exempt the original quest target too.
    return target;
}

bool QuestHunt::CanEngage(QuestSpawn const& target) const
{
    Creature* npc = Resolve(*bot, target);
    _safety.SetTarget(target.guid);
    return npc && Available(*bot, *npc) && !bot->IsInCombat() && !bot->IsMounted() &&
        !bot->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) &&
        !bot->IsNonMeleeSpellCasted(false) && EvaluateReadiness(ReadCombatReadiness(*bot), false).state == Preparation::Ready &&
        AssessRouteOpponent(*bot, *npc, false).allowed &&
        _safety.CanApproach(target) &&
        bot->IsWithinDistInMap(npc, 20.0f) && bot->IsWithinLOSInMap(npc);
}

bool QuestHunt::Engage(QuestSpawn const& target)
{
    // Caller releases its travel first. Do not let AttackAction clear a foreign
    // point/follow/scripted route while switching to the native combat engine.
    if (!CanEngage(target) || bot->GetMotionMaster()->GetCurrentMovementGeneratorType() != IDLE_MOTION_TYPE ||
        !bot->movespline->Finalized())
        return false;
    Creature* enemy = Resolve(*bot, target);
    if (!enemy)
        return false;
    CombatAssessment const assessment = AssessRouteOpponent(*bot, *enemy, false);
    if (!assessment.allowed || !Attack(enemy))
        return false; // Existing Playerbots engine owns spells, chase and melee.
    TC_LOG_INFO("playerbots.botlife", "BotLife assessment guid={} spawn={} allowed=true reason={} model={} mainhand={} offhand={} outgoingDps={} incomingDps={} seconds={} incoming={}",
        bot->GetGUID().GetCounter(), target.guid, assessment.reason, assessment.model,
        assessment.mainhandDps, assessment.offhandDps, assessment.outgoingDps, assessment.incomingDps,
        assessment.seconds, assessment.incomingDamage);
    return true;
}

bool QuestHunt::IsAlive(QuestSpawn const& target) const
{
    Creature* npc = Resolve(*bot, target);
    return npc && npc->IsAlive();
}

bool QuestHunt::IsFighting() const
{
    return bot->IsInCombat() || bot->GetVictim() || botAI->GetState() == BOT_STATE_COMBAT;
}
}
