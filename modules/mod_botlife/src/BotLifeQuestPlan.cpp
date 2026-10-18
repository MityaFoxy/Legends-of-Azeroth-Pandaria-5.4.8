#include "BotLifeQuestPlan.h"

#include <algorithm>
#include <cmath>
#include <limits>

namespace BotLife
{
namespace
{
std::optional<QuestSpawn> Nearest(std::vector<QuestSpawn> const& candidates, QuestPlayerSnapshot const& player)
{
    std::optional<QuestSpawn> best;
    double bestDistance = std::numeric_limits<double>::infinity();
    for (QuestSpawn const& spawn : candidates)
    {
        if (spawn.mapId != player.mapId || !(spawn.phaseMask & player.phaseMask) || !spawn.guid || !spawn.entry)
            continue;
        double const dx = double(spawn.x) - player.x, dy = double(spawn.y) - player.y, dz = double(spawn.z) - player.z;
        double const distance = dx * dx + dy * dy + dz * dz;
        if (std::isfinite(distance) && (distance < bestDistance ||
            (distance == bestDistance && best && spawn.guid < best->guid)))
        {
            best = spawn;
            bestDistance = distance;
        }
    }
    return best;
}
}

QuestPlan BuildQuestPlan(QuestPlanData const& data, QuestPlayerSnapshot const& player)
{
    QuestPlan plan;
    plan.questId = data.questId;
    auto reject = [&](QuestPlanReason reason) { plan.reason = reason; return plan; };
    if (data.error != QuestPlanReason::None)
        return reject(data.error);
    if (!player.validContext || !player.phaseMask || !std::isfinite(player.x) ||
        !std::isfinite(player.y) || !std::isfinite(player.z))
        return reject(QuestPlanReason::InvalidContext);
    if (player.progress == QuestProgress::Rewarded)
    {
        plan.stage = QuestPlanStage::Done;
        return plan;
    }
    if (player.progress == QuestProgress::Failed)
        return reject(QuestPlanReason::FailedQuest);
    if (player.eligibility != QuestPlanReason::None)
        return reject(player.eligibility);

    bool const acquire = player.progress == QuestProgress::NotTaken;
    plan.starter = Nearest(data.starters, player);
    plan.ender = Nearest(data.enders, player);
    if (acquire && !plan.starter)
        return reject(QuestPlanReason::MissingStarter);
    if (!plan.ender)
        return reject(QuestPlanReason::MissingEnder);

    bool remaining = false;
    for (QuestKillObjective const& objective : data.objectives)
    {
        auto const counter = player.counters.find(objective.id);
        uint32_t const done = acquire || counter == player.counters.end() ? 0 : counter->second;
        uint32_t const left = player.progress == QuestProgress::Complete ? 0 :
            objective.amount - std::min(objective.amount, done);
        plan.objectives.push_back({objective.id, objective.entry, objective.amount, left,
            left ? Nearest(objective.candidates, player) : std::nullopt});
        remaining |= left != 0;
    }
    for (QuestObjectivePlan const& objective : plan.objectives)
        if (objective.remaining && !objective.candidate)
            return reject(QuestPlanReason::MissingObjective);

    if (acquire)
        plan.stage = QuestPlanStage::Acquire;
    else if (player.progress == QuestProgress::Complete)
        plan.stage = QuestPlanStage::TurnIn;
    else
        plan.stage = remaining ? QuestPlanStage::Hunt : QuestPlanStage::AwaitCompletion;
    return plan;
}

char const* ToString(QuestPlanStage stage)
{
    switch (stage)
    {
        case QuestPlanStage::Rejected: return "Rejected";
        case QuestPlanStage::Acquire: return "Acquire";
        case QuestPlanStage::Hunt: return "Hunt";
        case QuestPlanStage::AwaitCompletion: return "AwaitCompletion";
        case QuestPlanStage::TurnIn: return "TurnIn";
        case QuestPlanStage::Done: return "Done";
    }
    return "Unknown";
}

char const* ToString(QuestPlanReason reason)
{
    switch (reason)
    {
        case QuestPlanReason::None: return "None";
        case QuestPlanReason::MissingQuest: return "MissingQuest";
        case QuestPlanReason::UnsupportedQuest: return "UnsupportedQuest";
        case QuestPlanReason::DataLimit: return "DataLimit";
        case QuestPlanReason::InvalidContext: return "InvalidContext";
        case QuestPlanReason::CatalogChanged: return "CatalogChanged";
        case QuestPlanReason::QuestDisabled: return "QuestDisabled";
        case QuestPlanReason::Level: return "Level";
        case QuestPlanReason::RaceOrClass: return "RaceOrClass";
        case QuestPlanReason::Prerequisites: return "Prerequisites";
        case QuestPlanReason::NativeEligibility: return "NativeEligibility";
        case QuestPlanReason::QuestLogFull: return "QuestLogFull";
        case QuestPlanReason::FailedQuest: return "FailedQuest";
        case QuestPlanReason::MissingStarter: return "MissingStarterCandidate";
        case QuestPlanReason::MissingObjective: return "MissingObjectiveCandidate";
        case QuestPlanReason::MissingEnder: return "MissingEnderCandidate";
    }
    return "Unknown";
}
}
