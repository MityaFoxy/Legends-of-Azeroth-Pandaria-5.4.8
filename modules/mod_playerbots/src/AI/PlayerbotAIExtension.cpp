#include "PlayerbotAIExtension.h"

#include <algorithm>
#include <utility>

PlayerbotAIExtensionRegistry* PlayerbotAIExtensionRegistry::instance()
{
    static PlayerbotAIExtensionRegistry registry;
    return &registry;
}

void PlayerbotAIExtensionRegistry::Register(Factory factory)
{
    if (!factory || std::find(_factories.begin(), _factories.end(), factory) != _factories.end())
        return;

    _factories.push_back(factory);
}

std::vector<std::unique_ptr<PlayerbotAIExtension>> PlayerbotAIExtensionRegistry::CreateExtensions() const
{
    std::vector<std::unique_ptr<PlayerbotAIExtension>> extensions;
    extensions.reserve(_factories.size());

    for (Factory factory : _factories)
    {
        if (std::unique_ptr<PlayerbotAIExtension> extension = factory())
            extensions.push_back(std::move(extension));
    }

    return extensions;
}
