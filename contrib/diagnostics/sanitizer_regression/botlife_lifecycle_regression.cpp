// Compile the production context/executor with small world-interface doubles.
// This does not substitute for integration testing against a running server.
#include "BotLife.h"
#include "Config.h"
#include "PlayerbotAI.h"

#include <cassert>
#include <iostream>
#include <limits>

using namespace BotLife;

namespace
{
struct Probe
{
    int starts = 0, updates = 0, pauses = 0, resumes = 0, interrupts = 0, finishes = 0;
    bool valid = true;
    bool ownsMovement = false;
    bool holdsNonCombat = false;
    bool recoverable = false, expired = false;
    int deaths = 0;
    InterruptReason reason = InterruptReason::Reset;
    ActivityResult result = ActivityResult::Running;
} probe;

class ProbeExecutor final : public ActivityExecutor
{
public:
    explicit ProbeExecutor(ActivityType type) : _type(type) { }
    ActivityType GetType() const override { return _type; }
    void Start(PlayerbotAI&) override { ++probe.starts; }
    ActivityResult Update(PlayerbotAI&, uint32_t) override { ++probe.updates; return probe.result; }
    void Pause(PlayerbotAI&) override { ++probe.pauses; }
    bool Resume(PlayerbotAI&) override { ++probe.resumes; return probe.valid; }
    bool SuspendForDeath(PlayerbotAI&) override { ++probe.deaths; probe.ownsMovement = false; return probe.recoverable; }
    bool IsDeathRecoveryExpired() const override { return probe.expired; }
    void Interrupt(PlayerbotAI&, InterruptReason reason) override { ++probe.interrupts; probe.reason = reason; }
    void Finish(PlayerbotAI&, ActivityResult) override { ++probe.finishes; }
    bool ControlsMovement() const override { return probe.ownsMovement; }
    bool HoldsNonCombat() const override { return probe.holdsNonCombat; }
private:
    ActivityType _type;
};

std::unique_ptr<ActivityExecutor> CreateProbe(ActivityType type, uint32_t)
{
    return std::make_unique<ProbeExecutor>(type);
}

std::unique_ptr<ActivityExecutor> CreateSingleProbe(PlayerbotAI&)
{
    return std::make_unique<ProbeExecutor>(ActivityType::Quest);
}

std::unique_ptr<ActivityExecutor> RejectSingleProbe(PlayerbotAI&) { return nullptr; }

void Tick(ActivityContext& context, PlayerbotAI& ai, uint32_t elapsed = 100)
{
    assert(context.Update(ai, elapsed) == PlayerbotAIExtensionResult::ContinueBaseAI);
}

template <typename Change>
void CheckCancellation(InterruptReason expected, Change change)
{
    testConfig = {};
    LoadConfig();
    probe = {};
    Player bot;
    PlayerbotAI ai{ &bot };
    ActivityContext context(&CreateProbe);
    Tick(context, ai);
    bot.combat = true;
    context.Observe(ai);
    assert(context.IsPaused());
    change(bot, ai);
    context.Observe(ai);
    assert(!context.IsActive() && !context.IsPaused());
    assert(context.GetActivity() == ActivityType::Free);
    assert(probe.interrupts == 1 && probe.reason == expected && probe.resumes == 0);
    context.Observe(ai);
    context.Reset(ai);
    assert(probe.interrupts == 1); // Cancellation is idempotent.
}
}

int main()
{
    {
        LoadConfig();
        Player serviceBot;
        PlayerbotAI serviceAI{&serviceBot};
        ActivityContext serviceContext(&CreateProbe);
        probe = {};
        probe.holdsNonCombat = true;
        assert(serviceContext.Update(serviceAI, 1) == PlayerbotAIExtensionResult::SuppressBaseNonCombatAction);
        assert(!probe.ownsMovement);
        serviceBot.combat = true;
        serviceContext.Observe(serviceAI);
        Tick(serviceContext, serviceAI); // Even a holding service cannot suppress combat.
        serviceContext.Reset(serviceAI);
        probe = {};
    }
    LoadConfig();
    Player bot, other;
    other.guid.value = 9;
    PlayerbotAI ai{ &bot }, otherAI{ &other };
    ActivityContext context(&CreateProbe), second;
    context.Observe(ai);
    assert(!context.IsActive() && probe.starts == 0); // Observer cannot start work.
    Tick(context, ai);
    Tick(second, otherAI, 500);
    bot.combat = true;
    context.Observe(ai);
    context.Observe(ai);
    Tick(context, ai, 100000);
    assert(context.IsPaused() && probe.pauses == 1 && probe.updates == 1);
    Tick(second, otherAI, 500);
    assert(second.GetActivity() == ActivityType::Quest); // Independent contexts.
    bot.combat = false;
    context.Observe(ai);
    assert(context.IsPaused() && probe.resumes == 0);
    Tick(context, ai, 100000);
    assert(!context.IsPaused() && probe.resumes == 1 && probe.updates == 1);
    Tick(context, ai);
    assert(probe.updates == 2);

    bot.combat = true;
    context.Observe(ai);
    bot.combat = false;
    probe.valid = false;
    Tick(context, ai);
    assert(!context.IsActive() && probe.reason == InterruptReason::InvalidTarget);
    Tick(context, ai);
    assert(context.IsActive() && context.GetActivity() == ActivityType::Free);
    probe.result = ActivityResult::TemporarilyBlocked;
    Tick(context, ai);
    assert(context.GetActivity() == ActivityType::Free);
    probe.result = ActivityResult::Completed;
    Tick(context, ai);
    assert(context.GetActivity() == ActivityType::Quest && probe.finishes == 1);
    probe.result = ActivityResult::Failed;
    Tick(context, ai);
    assert(context.GetActivity() == ActivityType::Free && probe.finishes == 2);
    context.Reset(ai);
    second.Reset(otherAI);

    CheckCancellation(InterruptReason::Death, [](Player& p, PlayerbotAI&) { p.alive = false; });
    CheckCancellation(InterruptReason::Teleport, [](Player& p, PlayerbotAI&) { p.teleport = true; });
    CheckCancellation(InterruptReason::OutOfWorld, [](Player& p, PlayerbotAI&) { p.inWorld = false; });
    CheckCancellation(InterruptReason::OutOfWorld, [](Player& p, PlayerbotAI&) { p.removing = true; });
    CheckCancellation(InterruptReason::Logout, [](Player& p, PlayerbotAI&) { p.session.loggingOut = true; });
    CheckCancellation(InterruptReason::Logout, [](Player& p, PlayerbotAI&) { p.hasSession = false; });
    CheckCancellation(InterruptReason::PlayerControl, [](Player&, PlayerbotAI& a) { a.playerMaster = true; });
    CheckCancellation(InterruptReason::WorldChanged, [](Player& p, PlayerbotAI&) { ++p.map; });
    CheckCancellation(InterruptReason::WorldChanged, [](Player& p, PlayerbotAI&) { ++p.instance; });
    CheckCancellation(InterruptReason::WorldChanged, [](Player& p, PlayerbotAI&) { ++p.phase; });
    CheckCancellation(InterruptReason::NotAllowed, [](Player&, PlayerbotAI& a) { a.bot = nullptr; });
    CheckCancellation(InterruptReason::NotAllowed, [](Player&, PlayerbotAI&) {
        testConfig.guids = "9";
        LoadConfig();
    });
    CheckCancellation(InterruptReason::Disabled, [](Player&, PlayerbotAI&) {
        testConfig.enabled = false;
        LoadConfig();
    });

    testConfig = {};
    LoadConfig();
    ActivityContext timer;
    bot = {};
    ai.bot = &bot;
    Tick(timer, ai, 400);
    bot.combat = true;
    timer.Observe(ai);
    Tick(timer, ai, std::numeric_limits<uint32_t>::max());
    bot.combat = false;
    Tick(timer, ai, std::numeric_limits<uint32_t>::max());
    Tick(timer, ai, 599);
    assert(timer.GetActivity() == ActivityType::Free);
    Tick(timer, ai, 1);
    assert(timer.GetActivity() == ActivityType::Quest); // Progress retained, pause excluded.
    Tick(timer, ai, 1000);
    assert(timer.GetActivity() == ActivityType::Town);
    Tick(timer, ai, 1000);
    assert(timer.GetActivity() == ActivityType::Rest);
    Tick(timer, ai, 1000);
    assert(timer.GetActivity() == ActivityType::Free);
    bot.alive = false;
    timer.Observe(ai);
    Tick(timer, ai);
    assert(!timer.IsActive());
    bot.alive = true;
    Tick(timer, ai);
    assert(timer.IsActive() && timer.GetActivity() == ActivityType::Free);
    timer.Reset(ai);

    bot.guid.value = 99;
    Tick(timer, ai);
    assert(!timer.IsActive());
    bot.guid.value = 14;
    bot.combat = true;
    Tick(timer, ai);
    assert(!timer.IsActive()); // No new activity during combat.
    // Suppression is opt-in and only applies while the active executor owns motion.
    probe = {};
    bot.combat = false;
    ActivityContext moving(&CreateProbe);
    Tick(moving, ai);
    probe.ownsMovement = true;
    assert(moving.Update(ai, 0) == PlayerbotAIExtensionResult::SuppressBaseNonCombatAction);
    bot.combat = true;
    moving.Observe(ai);
    Tick(moving, ai); // Lifecycle gates win even if an executor reports ownership.
    bot.combat = false;
    Tick(moving, ai); // Resume does not suppress a base action without a new update.
    probe.ownsMovement = false;
    Tick(moving, ai);
    moving.Reset(ai);
    // Single-run integration scenarios must not restart on finish, failure/reset,
    // cancellation, or rejected construction; normal timer mode is unchanged.
    for (ActivityResult result : {ActivityResult::Completed, ActivityResult::Failed})
    {
        probe = {};
        probe.result = result;
        ActivityContext single(&CreateProbe, &CreateSingleProbe);
        Tick(single, ai);
        assert(!single.IsActive() && probe.starts == 1 && probe.finishes == 1);
        assert(single.GetActivity() == ActivityType::Quest); // Single-run factory supplies its own activity type.
        single.Reset(ai);
        Tick(single, ai);
        assert(probe.starts == 1 && probe.updates == 1);
    }
    probe = {};
    ActivityContext cancelled(&CreateProbe, &CreateSingleProbe);
    Tick(cancelled, ai);
    cancelled.Reset(ai);
    Tick(cancelled, ai);
    assert(probe.starts == 1 && probe.interrupts == 1);
    ActivityContext rejected(&CreateProbe, &RejectSingleProbe);
    Tick(rejected, ai);
    Tick(rejected, ai);
    assert(!rejected.IsActive() && probe.starts == 1);

    // Opt-in quests retain one executor through combat -> death -> native ghost
    // transfer -> recovery. No actions/suppression during death or low-health rest.
    probe = {};
    probe.recoverable = true;
    bot = {};
    ActivityContext recovery(&CreateProbe, &CreateSingleProbe);
    Tick(recovery, ai);
    probe.ownsMovement = true;
    bot.combat = true;
    recovery.Observe(ai);
    bot.alive = false;
    recovery.Observe(ai);
    recovery.Observe(ai);
    Tick(recovery, ai, 900000);
    assert(probe.deaths == 1 && probe.starts == 1 && probe.updates == 1 && probe.interrupts == 0);
    assert(recovery.IsActive() && recovery.IsPaused());
    bot.combat = false;
    bot.ghost = bot.corpse = bot.teleport = true;
    Tick(recovery, ai); // A near transfer of a dead ghost with its corpse preserves the plan.
    assert(recovery.IsActive() && probe.interrupts == 0);
    bot.teleport = false;
    bot.alive = true;
    Tick(recovery, ai); // A lingering ghost flag must not resume quest actions.
    assert(probe.resumes == 0);
    bot.ghost = false;
    bot.health = 20;
    Tick(recovery, ai);
    assert(probe.resumes == 0);
    bot.health = 100;
    bot.combat = true;
    Tick(recovery, ai);
    assert(probe.resumes == 0);
    bot.combat = false;
    Tick(recovery, ai, 900000);
    assert(probe.resumes == 1 && probe.updates == 1 && !recovery.IsPaused());
    Tick(recovery, ai);
    assert(probe.updates == 2 && probe.starts == 1);
    bot.alive = false;
    recovery.Observe(ai);
    assert(probe.deaths == 2 && recovery.IsActive());
    probe.expired = true;
    recovery.Observe(ai);
    assert(!recovery.IsActive() && probe.reason == InterruptReason::RecoveryTimeout);
    bot.alive = true;
    Tick(recovery, ai);
    assert(probe.starts == 1); // Bounded recovery timeout is not an automatic retry.

    for (int mode = 0; mode < 12; ++mode)
    {
        probe = {};
        probe.recoverable = true;
        testConfig = {};
        LoadConfig();
        bot = {};
        ai.playerMaster = false;
        ActivityContext guarded(&CreateProbe, &CreateSingleProbe);
        Tick(guarded, ai);
        bot.alive = false;
        guarded.Observe(ai);
        switch (mode)
        {
            case 0: bot.teleport = true; break; // No ghost/corpse.
            case 1: bot.teleport = bot.ghost = bot.corpse = true; bot.nearTeleport = false; break;
            case 2: bot.alive = bot.teleport = true; break;
            case 3: ++bot.map; break;
            case 4: ++bot.instance; break;
            case 5: ++bot.phase; break;
            case 6: bot.inWorld = false; break;
            case 7: bot.session.loggingOut = true; break;
            case 8: ai.playerMaster = true; break;
            case 9: testConfig.enabled = false; LoadConfig(); break;
            case 10: testConfig.guids = "9"; LoadConfig(); break;
            case 11: guarded.Reset(ai); break;
        }
        guarded.Observe(ai);
        assert(!guarded.IsActive() && probe.interrupts == 1 && probe.resumes == 0);
        guarded.Reset(ai);
        assert(probe.interrupts == 1);
    }
    // Live regression: death -> native Refresh resurrection -> typed Reset -> later resume.
    testConfig = {};
    LoadConfig();
    probe = {};
    probe.recoverable = true;
    bot = {};
    ai.playerMaster = false;
    ActivityContext refreshed(&CreateProbe, &CreateSingleProbe);
    Tick(refreshed, ai);
    bot.combat = true;
    refreshed.Observe(ai);
    bot.alive = false;
    refreshed.Observe(ai);
    assert(probe.deaths == 1 && refreshed.IsPaused());
    bot.alive = true; // Refresh resurrects before its Reset call.
    bot.combat = false;
    PlayerbotAIExtension& extension = refreshed;
    extension.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    extension.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    assert(refreshed.IsActive() && refreshed.IsPaused());
    assert(probe.starts == 1 && probe.deaths == 1 && !probe.resumes && !probe.interrupts);
    Tick(refreshed, ai, 900000);
    assert(probe.resumes == 1 && probe.updates == 1 && probe.starts == 1);
    Tick(refreshed, ai);
    assert(probe.updates == 2);
    // Even a recovery-labelled reset cannot preserve a run that is no longer recovering.
    extension.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    assert(!refreshed.IsActive() && probe.reason == InterruptReason::Reset);
    Tick(refreshed, ai);
    assert(probe.starts == 1);

    for (int mode = 0; mode < 14; ++mode)
    {
        testConfig = {};
        LoadConfig();
        probe = {};
        probe.recoverable = true;
        bot = {};
        ai.playerMaster = false;
        ActivityContext guarded(&CreateProbe, &CreateSingleProbe);
        Tick(guarded, ai);
        bot.alive = false;
        guarded.Observe(ai);
        bot.alive = true;
        switch (mode)
        {
            case 0: ++bot.map; break;
            case 1: ++bot.instance; break;
            case 2: ++bot.phase; break;
            case 3: bot.inWorld = false; break;
            case 4: bot.removing = true; break;
            case 5: bot.hasSession = false; break;
            case 6: bot.session.loggingOut = true; break;
            case 7: ai.playerMaster = true; break;
            case 8: testConfig.enabled = false; LoadConfig(); break;
            case 9: testConfig.guids = "9"; LoadConfig(); break;
            case 10: bot.teleport = true; break;
            case 11: probe.expired = true; break;
            case 12: guarded.Reset(ai); break; // Explicit reset / destruction still cancel.
            case 13: guarded.Reset(ai, PlayerbotAIResetReason::General); break;
        }
        guarded.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
        assert(!guarded.IsActive() && probe.interrupts == 1 && !probe.resumes);
        guarded.Reset(ai);
        assert(probe.interrupts == 1);
    }

    // Recovery reset must not replenish its deadline while combat/rest still blocks resumption.
    testConfig = {};
    LoadConfig();
    probe = {};
    probe.recoverable = true;
    bot = {};
    ai.playerMaster = false;
    ActivityContext waiting(&CreateProbe, &CreateSingleProbe);
    Tick(waiting, ai);
    bot.alive = false;
    waiting.Observe(ai);
    bot.alive = true;
    bot.health = 20;
    waiting.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    Tick(waiting, ai);
    assert(waiting.IsPaused() && !probe.resumes && probe.deaths == 1);
    probe.expired = true;
    waiting.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    assert(!waiting.IsActive() && probe.reason == InterruptReason::RecoveryTimeout);

    struct LegacyExtension final : PlayerbotAIExtension
    {
        int resets = 0;
        PlayerbotAIExtensionResult Update(PlayerbotAI&, uint32_t) override
        { return PlayerbotAIExtensionResult::ContinueBaseAI; }
        void Reset(PlayerbotAI&) override { ++resets; }
    } legacy;
    static_cast<PlayerbotAIExtension&>(legacy).Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
    assert(legacy.resets == 1); // Non-opted-in extensions retain their original semantics.

    // Disabled / non-allowlisted BotLife never starts or suppresses the ordinary AI,
    // including after a recovery-labelled reset with no active quest.
    for (bool disabled : {false, true})
    {
        testConfig = {};
        testConfig.enabled = !disabled;
        if (!disabled)
            testConfig.guids = "9";
        LoadConfig();
        probe = {};
        bot = {};
        ActivityContext inactive(&CreateProbe, &CreateSingleProbe);
        Tick(inactive, ai);
        bot.alive = false;
        inactive.Observe(ai);
        bot.alive = true;
        inactive.Reset(ai, PlayerbotAIResetReason::DeathRecoveryRefresh);
        Tick(inactive, ai);
        assert(!inactive.IsActive() && !probe.starts && !probe.interrupts && !probe.resumes);
    }
    std::cout << "BotLife lifecycle and timer regressions passed\n";
}
