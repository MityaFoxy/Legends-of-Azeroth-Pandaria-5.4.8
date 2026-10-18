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
    void Interrupt(PlayerbotAI&, InterruptReason reason) override { ++probe.interrupts; probe.reason = reason; }
    void Finish(PlayerbotAI&, ActivityResult) override { ++probe.finishes; }
private:
    ActivityType _type;
};

std::unique_ptr<ActivityExecutor> CreateProbe(ActivityType type, uint32_t)
{
    return std::make_unique<ProbeExecutor>(type);
}

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
    std::cout << "BotLife lifecycle and timer regressions passed\n";
}
