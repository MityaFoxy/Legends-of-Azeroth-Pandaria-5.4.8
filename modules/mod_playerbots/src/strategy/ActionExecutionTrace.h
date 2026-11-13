#ifndef PLAYERBOT_ACTION_EXECUTION_TRACE_H
#define PLAYERBOT_ACTION_EXECUTION_TRACE_H

#include <cstdint>

class Action;
class Player;
class Unit;

// Opt-in observation of one Engine execution, not another Action result.
// Nested executions restore the parent frame; no reason survives to the next
// execution. A disabled inner execution must not write into its parent either.
class ActionExecutionTrace
{
public:
    explicit ActionExecutionTrace(bool enabled) : previous(current), enabled(enabled)
    {
        current = enabled ? this : nullptr;
    }
    ~ActionExecutionTrace() { current = previous; }
    ActionExecutionTrace(ActionExecutionTrace const&) = delete;
    ActionExecutionTrace& operator=(ActionExecutionTrace const&) = delete;

    static bool Fail(char const* cause)
    {
        if (current)
        {
            current->detail = current->reason;
            current->reason = cause;
        }
        return false;
    }
    static void Spell(std::uint32_t id, std::int32_t result = -1)
    {
        if (current)
        {
            current->spellId = id;
            current->castResult = result;
        }
    }
    static void Target(Unit const* target);
    static bool Enabled();
    static void RawResult(bool result) { if (current) current->rawResult = result; }
    bool GetRawResult() const { return rawResult; }
    void Finish(Player const* bot, Action* action, bool rawResult, bool finalResult) const;

private:
    inline static thread_local ActionExecutionTrace* current = nullptr;
    ActionExecutionTrace* previous;
    bool enabled;
    bool rawResult = false;
    char const* reason = "unattributed";
    char const* detail = "none";
    std::uint32_t spellId = 0;
    std::int32_t castResult = -1;
    std::uint32_t targetGuid = 0, targetMap = 0, targetInstance = 0, targetType = 0;
    bool targetAlive = false, targetMoving = false;
    float targetX = 0, targetY = 0, targetZ = 0;
};

#endif
