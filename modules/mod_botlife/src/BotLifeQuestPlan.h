#ifndef _BOTLIFE_QUEST_PLAN_H
#define _BOTLIFE_QUEST_PLAN_H

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace BotLife
{
enum class QuestPlanStage { Rejected, Acquire, Hunt, Interact, AwaitCompletion, TurnIn, Done };
enum class QuestProgress { NotTaken, Active, Complete, Failed, Rewarded };
enum class QuestPlanReason
{
    None, MissingQuest, UnsupportedQuest, DataLimit, InvalidContext, CatalogChanged,
    QuestDisabled, Level, RaceOrClass, Prerequisites, NativeEligibility, QuestLogFull,
    FailedQuest, MissingStarter, MissingObjective, MissingEnder
};

// Database candidates only: neither a live object nor a verified route/interaction.
struct QuestSpawn
{
    uint32_t guid = 0, entry = 0, mapId = 0, phaseMask = 0;
    float x = 0, y = 0, z = 0;
};

enum class QuestObjectiveKind { Kill, Loot, GameObject };

struct QuestObjectiveData
{
    uint32_t id = 0, entry = 0, amount = 0;
    std::vector<QuestSpawn> candidates;
    QuestObjectiveKind kind = QuestObjectiveKind::Kill;
};

// Owned values, shared read-only after startup. Never retains Quest/Creature pointers.
struct QuestPlanData
{
    uint32_t questId = 0;
    std::string title;
    QuestPlanReason error = QuestPlanReason::MissingQuest;
    std::vector<QuestSpawn> starters, enders;
    std::vector<QuestObjectiveData> objectives;

    bool HasLootObjective() const { return !objectives.empty() && objectives.front().kind == QuestObjectiveKind::Loot; }
    bool HasObjectObjective() const { return !objectives.empty() && objectives.front().kind == QuestObjectiveKind::GameObject; }
};

struct QuestPlayerSnapshot
{
    QuestProgress progress = QuestProgress::NotTaken;
    QuestPlanReason eligibility = QuestPlanReason::None;
    bool validContext = false;
    uint32_t mapId = 0, phaseMask = 0;
    float x = 0, y = 0, z = 0;
    std::unordered_map<uint32_t, uint32_t> counters;
};

struct QuestObjectivePlan
{
    uint32_t id = 0, entry = 0, required = 0, remaining = 0;
    std::optional<QuestSpawn> candidate;
};

struct QuestPlan
{
    uint32_t questId = 0;
    QuestPlanStage stage = QuestPlanStage::Rejected;
    QuestPlanReason reason = QuestPlanReason::None;
    std::optional<QuestSpawn> starter, ender;
    std::vector<QuestObjectivePlan> objectives;
};

QuestPlan BuildQuestPlan(QuestPlanData const& data, QuestPlayerSnapshot const& player);
std::optional<QuestSpawn> FindNearestQuestSpawn(std::vector<QuestSpawn> const& candidates, QuestPlayerSnapshot const& player,
    std::unordered_set<uint32_t> const* excluded = nullptr);
char const* ToString(QuestPlanStage stage);
char const* ToString(QuestPlanReason reason);
}
#endif
