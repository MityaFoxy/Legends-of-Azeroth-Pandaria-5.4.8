#include "BotLifeDefeats.h"
#include <algorithm>
#include <cmath>

namespace BotLife
{
uint32_t AreaDefeatHistory::Record(DefeatArea area, uint32_t now)
{
    std::erase_if(_areas, [now](auto const& row) { return uint32_t(now-row.at) >= DefeatHistory::LifetimeMs; });
    if (!std::isfinite(area.origin.x) || !std::isfinite(area.origin.y) || !std::isfinite(area.origin.z))
        return 0;
    area.at = now;
    area.deaths = 1;
    auto nearest = _areas.end();
    float distance = MergeRadius * MergeRadius;
    for (auto it = _areas.begin(); it != _areas.end(); ++it)
    {
        float const dx = it->origin.x-area.origin.x, dy = it->origin.y-area.origin.y;
        if (it->map == area.map && it->instance == area.instance && it->phase == area.phase &&
            std::abs(it->origin.z-area.origin.z) <= Height && dx*dx+dy*dy <= distance)
        {
            nearest = it;
            distance = dx*dx+dy*dy;
        }
    }
    if (nearest != _areas.end())
    {
        area.origin = nearest->origin; // Fixed first anchor prevents chain-merging a whole camp.
        area.deaths = std::min(DefeatHistory::Threshold, nearest->deaths+1);
        _areas.erase(nearest);
    }
    if (_areas.size() == DefeatHistory::Capacity)
        _areas.pop_front();
    _areas.push_back(area);
    return area.deaths;
}

std::vector<DefeatArea> AreaDefeatHistory::Active(uint32_t map, uint32_t instance, uint32_t phase, uint32_t now)
{
    std::erase_if(_areas, [now](auto const& row) { return uint32_t(now-row.at) >= DefeatHistory::LifetimeMs; });
    std::vector<DefeatArea> result;
    for (auto const& row : _areas)
        if (row.map == map && row.instance == instance && row.phase == phase && row.deaths >= DefeatHistory::Threshold)
            result.push_back(row);
    return result;
}

void DefeatHistory::Expire(uint32_t now)
{
    std::erase_if(_entries, [now](Entry const& row) { return uint32_t(now - row.at) >= LifetimeMs; });
}

uint32_t DefeatHistory::Record(OpponentKey key, uint32_t now)
{
    Expire(now);
    if (!key.identity)
        return 0;
    uint32_t deaths = 1;
    for (auto it = _entries.begin(); it != _entries.end(); ++it)
        if (it->key == key)
        {
            deaths = std::min(Threshold, it->deaths + 1);
            _entries.erase(it);
            break;
        }
    if (_entries.size() == Capacity)
        _entries.pop_front();
    _entries.push_back({key, now, deaths});
    return deaths;
}

bool DefeatHistory::Avoid(OpponentKey key, uint32_t now)
{
    Expire(now);
    return std::any_of(_entries.begin(), _entries.end(), [&](Entry const& row)
        { return row.key == key && row.deaths >= Threshold; });
}
}
