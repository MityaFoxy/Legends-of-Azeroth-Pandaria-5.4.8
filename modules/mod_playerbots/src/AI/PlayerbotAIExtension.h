#ifndef _PLAYERBOT_AI_EXTENSION_H
#define _PLAYERBOT_AI_EXTENSION_H

#include <cstdint>
#include <memory>
#include <vector>

class PlayerbotAI;

enum class PlayerbotAIExtensionResult : uint8_t
{
    ContinueBaseAI,
    SuppressBaseNonCombatAction
};

class PlayerbotAIExtension
{
public:
    virtual ~PlayerbotAIExtension() = default;

    virtual PlayerbotAIExtensionResult Update(PlayerbotAI& botAI, uint32_t elapsed) = 0;
    virtual void Reset(PlayerbotAI& botAI) = 0;
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
