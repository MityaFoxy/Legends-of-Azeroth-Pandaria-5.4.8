#pragma once

#include <string_view>
#include <vector>

namespace Trinity
{
inline std::vector<std::string_view> Tokenize(std::string_view input, char delimiter, bool)
{
    std::vector<std::string_view> result;
    while (!input.empty())
    {
        auto end = input.find(delimiter);
        result.push_back(input.substr(0, end));
        if (end == std::string_view::npos)
            break;
        input.remove_prefix(end + 1);
    }
    return result;
}
}
