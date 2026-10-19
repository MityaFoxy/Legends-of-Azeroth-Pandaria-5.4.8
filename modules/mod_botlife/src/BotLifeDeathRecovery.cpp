#include "BotLife.h"

#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"

namespace BotLife
{
void ActivityContext::Reset(PlayerbotAI& ai, PlayerbotAIResetReason reason)
{
    if (reason == PlayerbotAIResetReason::DeathRecoveryRefresh && _active && _recoveringFromDeath)
    {
        // Refresh has resurrected the bot but has not finished resetting its base AI.
        // Revalidate gates now; resume only on a later Update, never inside Reset.
        CheckLifecycle(ai);
        if (_active && _recoveringFromDeath)
        {
            TC_LOG_INFO("playerbots.botlife", "BotLife bot={} event=recovery-reset reason=death-recovery-refresh preserved=true",
                ai.GetBot()->GetGUID().GetCounter());
            return; // Keep the same executor, counters and original recovery deadline.
        }
        return; // A lifecycle gate has already cancelled the activity with its own reason.
    }
    Reset(ai);
}

bool ActivityContext::CheckDeathRecovery(PlayerbotAI& ai)
{
    // Called only after session, world, allowlist, control and map/phase guards.
    Player& bot = *ai.GetBot();
    if (!bot.IsAlive() && _active && !_recoveringFromDeath)
    {
        if (!_executor->SuspendForDeath(ai))
        {
            Stop(ai, InterruptReason::Death);
            return false;
        }
        _recoveringFromDeath = _paused = true;
        TC_LOG_INFO("playerbots.botlife", "BotLife bot={} guid={} activity={} event=pause reason=death duration_ms={}",
            bot.GetName(), bot.GetGUID().ToString(), ToString(_activity), _elapsed);
    }
    if (_recoveringFromDeath && _executor->IsDeathRecoveryExpired())
    {
        Stop(ai, InterruptReason::RecoveryTimeout);
        return false;
    }
    if (bot.IsBeingTeleported())
    {
        // Observe (never issue) the core's same-map graveyard transfer of a ghost.
        // Far transfers, living teleports and transfers without a corpse still cancel.
        if (!(_recoveringFromDeath && !bot.IsAlive() && bot.IsBeingTeleportedNear() &&
            bot.HasPlayerFlag(PLAYER_FLAGS_GHOST) && bot.GetCorpse()))
            Stop(ai, InterruptReason::Teleport);
        return false;
    }
    if (!bot.IsAlive())
        return false; // ContinueBaseAI: its dead engine owns the entire corpse run.
    if (_recoveringFromDeath && (bot.HasPlayerFlag(PLAYER_FLAGS_GHOST) || bot.IsInCombat() || bot.GetHealthPct() < 50.0f))
        return false; // Native combat/rest first; still covered by recovery timeout.
    return true;
}
}
