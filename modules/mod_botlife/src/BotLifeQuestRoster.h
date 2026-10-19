#ifndef _BOTLIFE_QUEST_ROSTER_H
#define _BOTLIFE_QUEST_ROSTER_H

#include <charconv>
#include <cstdint>
#include <map>
#include <string_view>

namespace BotLife
{
// Strict, bounded explicit test configuration; not an autonomous quest scheduler.
inline std::map<uint32_t, uint32_t> ParseQuestRoster(std::string_view input)
{
    std::map<uint32_t, uint32_t> result;
    auto number = [](std::string_view text, uint32_t& value)
    {
        if (text.empty())
            return false;
        auto const parsed = std::from_chars(text.data(), text.data() + text.size(), value);
        return parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size() && value;
    };
    if (input.size() > 128)
        return {};
    while (!input.empty())
    {
        size_t const comma = input.find(',');
        std::string_view const pair = input.substr(0, comma);
        size_t const colon = pair.find(':');
        uint32_t guid = 0, quest = 0;
        if (colon == pair.npos || !number(pair.substr(0, colon), guid) ||
            !number(pair.substr(colon + 1), quest) || !result.emplace(guid, quest).second || result.size() > 5)
            return {};
        if (comma == input.npos)
            break;
        input.remove_prefix(comma + 1);
        if (input.empty())
            return {};
    }
    return result;
}
}
#endif
