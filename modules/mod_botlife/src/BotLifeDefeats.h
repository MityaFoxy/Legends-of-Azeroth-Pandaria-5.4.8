#ifndef _BOTLIFE_DEFEATS_H
#define _BOTLIFE_DEFEATS_H

#include <cstdint>
#include <deque>
#include <vector>

class Player;
class Creature;

namespace BotLife
{
struct OpponentKey
{
    uint32_t map = 0, instance = 0, entry = 0;
    uint64_t identity = 0;
    bool persistent = false;
    bool operator==(OpponentKey const&) const = default;
};

// Value-only, bounded memory. Runtime ownership and synchronization live in
// the adapter, not in the pure policy. Times use wrapping monotonic uint32 ms.
class DefeatHistory
{
public:
    static constexpr uint32_t LifetimeMs = 15 * 60 * 1000;
    static constexpr uint32_t Threshold = 2;
    static constexpr unsigned Capacity = 16;
    uint32_t Record(OpponentKey key, uint32_t now);
    bool Avoid(OpponentKey key, uint32_t now);
private:
    void Expire(uint32_t now);
    struct Entry { OpponentKey key; uint32_t at, deaths; };
    std::deque<Entry> _entries;
};

bool AvoidDefeatedOpponent(Player const& bot, Creature const& enemy);
struct DefeatPoint { float x = 0, y = 0, z = 0; };
struct DefeatArea
{
    uint32_t map = 0, instance = 0, phase = 0;
    DefeatPoint origin, death;
    uint32_t at = 0, deaths = 0;
};
// Small, fixed regions: never merge by template, grow a radius or drift the anchor.
class AreaDefeatHistory
{
public:
    static constexpr float Radius = 10, MergeRadius = 8, Height = 4;
    uint32_t Record(DefeatArea area, uint32_t now);
    std::vector<DefeatArea> Active(uint32_t map, uint32_t instance, uint32_t phase, uint32_t now);
private:
    std::deque<DefeatArea> _areas;
};
std::vector<DefeatArea> GetDefeatAreas(Player const& bot);
void RegisterDefeatMemoryScript();
}
#endif
