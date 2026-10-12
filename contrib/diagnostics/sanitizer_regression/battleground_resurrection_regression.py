#!/usr/bin/env python3
"""Run the real native BG wave/queue bodies through repeated deaths under ASan.

Player doubles model the 2584 removal callback into the BG queue. This checks
queue/aura lifetime, not spell DBC contents or live graveyard navigation.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
bg = (root / "src/server/game/Battlegrounds/Battleground.cpp").read_text()
remove_at_leave = bg[bg.index("void Battleground::RemovePlayerAtLeave("):
    bg.index("void Battleground::Reset()")]
assert "!player->IsAlive() || player->HasPlayerFlag(PLAYER_FLAGS_GHOST)" in remove_at_leave


def body(signature):
    start = bg.index(signature)
    end = bg.index("{", start) + 1
    depth = 1
    while depth:
        depth += (bg[end] == "{") - (bg[end] == "}")
        end += 1
    return bg[start:end]


source = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <map>
#include <vector>
using uint32 = std::uint32_t;
using ObjectGuid = unsigned;
constexpr uint32 RESURRECTION_INTERVAL = 30000;
constexpr int SPELL_WAITING_FOR_RESURRECT = 2584, SPELL_SPIRIT_HEAL = 22012,
    SPELL_RESURRECTION_VISUAL = 24171, SPELL_SPIRIT_HEAL_MANA = 44535;
struct Creature {
    int visuals = 0;
    void CastSpell(Creature*, int spell, bool triggered) {
        assert(spell == SPELL_SPIRIT_HEAL && triggered); ++visuals;
    }
};
struct Map {
    Creature guide;
    Creature* GetCreature(ObjectGuid) { return &guide; }
};
struct Battleground;
struct Player {
    ObjectGuid guid;
    Battleground* bg;
    Map* map;
    bool alive = false, waiting = false, world = true;
    int resurrects = 0, visuals = 0, mana = 0, bones = 0, removals = 0;
    bool IsInWorld() { return world; }
    Map* GetMap() { return map; }
    void CastSpell(Player*, int spell, bool triggered) {
        assert(triggered);
        if (spell == SPELL_WAITING_FOR_RESURRECT) waiting = true;
        else if (spell == SPELL_RESURRECTION_VISUAL) ++visuals;
        else { assert(spell == SPELL_SPIRIT_HEAL_MANA); ++mana; }
    }
    void ResurrectPlayer(float amount) { assert(amount == 1.0f); alive = true; ++resurrects; }
    void SpawnCorpseBones(bool save) { assert(!save); ++bones; }
    void RemoveAurasDueToSpell(int spell);
};
namespace ObjectAccessor {
    std::map<ObjectGuid, Player*> players;
    Player* FindPlayer(ObjectGuid guid) {
        auto i = players.find(guid); return i == players.end() ? nullptr : i->second;
    }
}
struct Battleground {
    uint32 m_LastResurrectTime = 0;
    std::map<ObjectGuid, std::vector<ObjectGuid>> m_ReviveQueue;
    std::vector<ObjectGuid> m_ResurrectQueue;
    size_t GetReviveQueueSize() { return m_ReviveQueue.size(); }
    void ProcessRessurect(uint32 diff);
    void AddPlayerToResurrectQueue(ObjectGuid npc_guid, ObjectGuid player_guid);
    void RemovePlayerFromResurrectQueue(ObjectGuid player_guid);
};
void Player::RemoveAurasDueToSpell(int spell) {
    assert(spell == SPELL_WAITING_FOR_RESURRECT);
    if (!waiting) return;
    waiting = false; ++removals;
    // SpellAuraEffects.cpp:2584 removes the player from its native queue.
    bg->RemovePlayerFromResurrectQueue(guid);
}
'''
for signature in ("void Battleground::ProcessRessurect(",
                  "void Battleground::AddPlayerToResurrectQueue(",
                  "void Battleground::RemovePlayerFromResurrectQueue("):
    source += body(signature)
source += r'''
int main() {
    Battleground bg;
    Map map;
    Player a{1, &bg, &map}, b{2, &bg, &map};
    ObjectAccessor::players = {{1, &a}, {2, &b}};
    for (int death = 1; death <= 3; ++death) {
        a.alive = b.alive = false;
        // Bot/client waits while aura 2584 is present: stale aura blocks requeue.
        assert(!a.waiting && !b.waiting);
        bg.AddPlayerToResurrectQueue(10, a.guid);
        bg.AddPlayerToResurrectQueue(10, b.guid);
        assert(a.waiting && b.waiting);
        bg.ProcessRessurect(RESURRECTION_INTERVAL - bg.m_LastResurrectTime);
        assert(!a.alive && !b.alive && bg.m_ReviveQueue.empty());
        bg.ProcessRessurect(500);
        assert(!a.alive && !b.alive); // Native half-second visual delay unchanged.
        bg.ProcessRessurect(1);
        assert(a.alive && b.alive && !a.waiting && !b.waiting);
        assert(a.resurrects == death && b.resurrects == death);
        assert(a.bones == death && a.mana == death && a.removals == death);
        assert(bg.m_ResurrectQueue.empty());
    }
    assert(map.guide.visuals == 3);
    // Cancellation callback is repeatable and leaves the other player's queue.
    a.alive = b.alive = false;
    bg.AddPlayerToResurrectQueue(10, a.guid);
    bg.AddPlayerToResurrectQueue(10, b.guid);
    a.RemoveAurasDueToSpell(SPELL_WAITING_FOR_RESURRECT);
    bg.RemovePlayerFromResurrectQueue(a.guid);
    assert(!a.waiting && b.waiting && bg.m_ReviveQueue.at(10).size() == 1);
    bg.ProcessRessurect(RESURRECTION_INTERVAL);
    // New arrivals during the visual delay must survive another player's aura callback.
    bg.AddPlayerToResurrectQueue(11, a.guid);
    bg.ProcessRessurect(501);
    assert(!a.alive && a.waiting && b.alive && !b.waiting);
    assert(bg.m_ReviveQueue.at(11).size() == 1);
    bg.ProcessRessurect(RESURRECTION_INTERVAL);
    ObjectAccessor::players.erase(a.guid); // Offline during the visual delay.
    bg.ProcessRessurect(501);
    assert(bg.m_ResurrectQueue.empty());
    bg.ProcessRessurect(RESURRECTION_INTERVAL);
    // Leaving during the native half-second visual delay must cancel the
    // second-stage queue and its waiting aura as well as the first-stage queue.
    ObjectAccessor::players[a.guid] = &a;
    a.alive = false;
    bg.AddPlayerToResurrectQueue(12, a.guid);
    bg.ProcessRessurect(RESURRECTION_INTERVAL - bg.m_LastResurrectTime);
    assert(!bg.m_ResurrectQueue.empty() && a.waiting);
    int resurrectsBeforeLeave = a.resurrects;
    bg.RemovePlayerFromResurrectQueue(a.guid);
    assert(bg.m_ResurrectQueue.empty() && !a.waiting);
    bg.ProcessRessurect(501);
    assert(a.resurrects == resurrectsBeforeLeave);
    std::puts("BG waves, three death/resurrection cycles, aura callback and offline player: OK");
}
'''
with tempfile.TemporaryDirectory(prefix="loa-bg-resurrection-") as directory:
    cpp = Path(directory) / "regression.cpp"
    exe = Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
