#ifndef _PLAYERBOT_AI_EXTENSION_H
#define _PLAYERBOT_AI_EXTENSION_H

#include <cstdint>
#include <memory>
#include <vector>

class PlayerbotAI;

enum class PlayerbotAIResetReason : uint8_t
{
    General,
    DeathRecoveryRefresh
};

enum class PlayerbotAIExtensionResult : uint8_t
{
    ContinueBaseAI,
    SuppressBaseNonCombatAction
};

class PlayerbotAIExtension
{
public:
    virtual ~PlayerbotAIExtension() = default;

    // Observe lifecycle even when the normal action tick is throttled/casting.
    // May pause/cancel existing work, but must not start gameplay actions.
    virtual void Observe(PlayerbotAI&) { }
    virtual PlayerbotAIExtensionResult Update(PlayerbotAI& botAI, uint32_t elapsed) = 0;
    virtual void Reset(PlayerbotAI& botAI) = 0;
    // Existing extensions remain cancel-on-reset unless they explicitly opt in.
    virtual void Reset(PlayerbotAI& botAI, PlayerbotAIResetReason) { Reset(botAI); }
};

class PlayerbotAIExtensionRegistry
{
public:
    using Factory = std::unique_ptr<PlayerbotAIExtension> (*)();

    static PlayerbotAIExtensionRegistry* instance();

    void Register(Factory factory);
    std::vector<std::unique_ptr<PlayerbotAIExtension>> CreateExtensions() const;

private:
    std::vector<Factory> _factories;
};

#define sPlayerbotAIExtensionRegistry PlayerbotAIExtensionRegistry::instance()

#endif
