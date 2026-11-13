#!/usr/bin/env python3
"""Run real native BG wave/queue/relocation bodies under ASan and checked STL.

Player doubles model the 2584 removal callback into the BG queue. This checks
queue/aura lifetime, not spell DBC contents or live graveyard navigation.
--verify-mutations rejects stale-aura and callback-unsafe relocation variants.
"""
from pathlib import Path
import subprocess
import os
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
#include <functional>
#include <map>
#include <set>
#include <vector>
// Logging is observational; the real build checks its core GUID/format types.
#define TC_LOG_INFO(...) ((void)0)
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
    uint32 mapId = 529;
    Creature guide;
    Creature* GetCreature(ObjectGuid) { return &guide; }
};
struct Battleground;
struct WorldSafeLocsEntry { float x = 10, y = 20, z = 30; };
struct Player {
    ObjectGuid guid;
    Battleground* bg;
    Map* map;
    bool alive = false, waiting = false, world = true;
    int resurrects = 0, visuals = 0, mana = 0, bones = 0, removals = 0;
    int teleports = 0;
    bool teleportSucceeds = true;
    std::function<void()> onTeleport;
    bool IsInWorld() { return world; }
    bool IsAlive() { return alive; }
    Battleground* GetBattleground() { return bg; }
    float GetOrientation() { return 1.5f; }
    bool TeleportTo(uint32 mapId, float x, float y, float z, float orientation) {
        // Aura must be cleared before the move, without forcing resurrection.
        assert(!waiting && !alive);
        assert(mapId == map->mapId && x == 10 && y == 20 && z == 30 && orientation == 1.5f);
        ++teleports;
        if (onTeleport) onTeleport();
        return teleportSucceeds;
    }
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
    void RelocateDeadPlayers(ObjectGuid queueIndex);
    WorldSafeLocsEntry grave;
    bool hasGraveyard = true;
    uint32 mapId = 529;
    uint32 GetMapId() { return mapId; }
    WorldSafeLocsEntry const* GetClosestGraveYard(Player*) { return hasGraveyard ? &grave : nullptr; }
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
                  "void Battleground::RemovePlayerFromResurrectQueue(",
                  "void Battleground::RelocateDeadPlayers("):
    source += body(signature)
source += r'''
void relocationChecks(uint32 mapId) {
    Battleground bg, otherBg;
    Map map;
    bg.mapId = otherBg.mapId = map.mapId = mapId;
    Player a{1, &bg, &map}, b{2, &bg, &map}, c{3, &bg, &map}, d{4, &bg, &map};
    Player foreign{5, &otherBg, &map}, alive{6, &bg, &map};
    ObjectAccessor::players = {{1, &a}, {2, &b}, {3, &c}, {4, &d}, {5, &foreign}, {6, &alive}};

    // Several ghosts from a lost node; callbacks must not invalidate iteration.
    bg.AddPlayerToResurrectQueue(10, a.guid);
    bg.AddPlayerToResurrectQueue(10, b.guid);
    bg.AddPlayerToResurrectQueue(11, c.guid);
    d.waiting = true; bg.m_ResurrectQueue.push_back(d.guid); // Another node's visual-delay stage.
    bg.m_LastResurrectTime = 1234;
    bg.RelocateDeadPlayers(10);
    assert(a.teleports == 1 && b.teleports == 1);
    assert(!a.waiting && !b.waiting && !a.alive && !b.alive);
    assert(c.waiting && bg.m_ReviveQueue.at(11) == std::vector<ObjectGuid>{c.guid});
    assert(d.waiting && bg.m_ResurrectQueue == std::vector<ObjectGuid>{d.guid});
    assert(bg.m_LastResurrectTime == 1234); // Do not reset the global wave clock.
    auto queueSize = bg.m_ReviveQueue.size();
    bg.RelocateDeadPlayers(10); bg.RelocateDeadPlayers(999);
    assert(bg.m_ReviveQueue.size() == queueSize && a.teleports == 1 && b.teleports == 1);

    // Normal new-guide registration; visual delay and native wave are retained.
    bg.AddPlayerToResurrectQueue(12, a.guid);
    bg.AddPlayerToResurrectQueue(12, b.guid);
    bg.ProcessRessurect(1); // Completes d's unrelated visual-delay stage only.
    assert(d.alive && !d.waiting && !a.alive && !b.alive && !c.alive);
    bg.ProcessRessurect(RESURRECTION_INTERVAL - bg.m_LastResurrectTime);
    assert(!a.alive && !b.alive && !c.alive);
    // Already selected for this wave: losing the old node must not cancel it.
    bg.RelocateDeadPlayers(12);
    assert(bg.m_ResurrectQueue.size() == 3);
    bg.ProcessRessurect(500); assert(!a.alive);
    bg.ProcessRessurect(1);
    assert(a.alive && b.alive && c.alive && !a.waiting && !b.waiting && !c.waiting);
    assert(a.resurrects == 1 && b.resurrects == 1 && c.resurrects == 1);

    // Callback can repopulate the old map key. Cleanup must not erase new work.
    a.alive = false;
    bg.AddPlayerToResurrectQueue(20, a.guid);
    bg.m_ReviveQueue[20].push_back(a.guid); // Duplicate registration must move once.
    a.onTeleport = [&] { bg.AddPlayerToResurrectQueue(20, a.guid); };
    bg.RelocateDeadPlayers(20);
    assert(a.teleports == 2 && a.waiting);
    assert(bg.m_ReviveQueue.at(20) == std::vector<ObjectGuid>{a.guid});
    a.onTeleport = {};
    bg.RemovePlayerFromResurrectQueue(a.guid);

    // Offline/stale entries and an alive player must not be teleported.
    foreign.waiting = true; alive.alive = true; alive.waiting = true;
    bg.m_ReviveQueue[30] = {404, foreign.guid, alive.guid};
    bg.RelocateDeadPlayers(30);
    assert(foreign.waiting && foreign.teleports == 0); // Other BG's aura is untouched.
    assert(alive.alive && !alive.waiting && alive.teleports == 0);
    assert(bg.m_ReviveQueue.find(30) == bg.m_ReviveQueue.end());

    // Missing destination or failed transfer must not leave a lying waiting aura.
    b.alive = false; bg.hasGraveyard = false;
    bg.AddPlayerToResurrectQueue(40, b.guid);
    bg.RelocateDeadPlayers(40);
    assert(!b.waiting && b.teleports == 1 && !b.alive);
    bg.hasGraveyard = true; b.teleportSucceeds = false;
    bg.AddPlayerToResurrectQueue(41, b.guid);
    bg.RelocateDeadPlayers(41);
    assert(!b.waiting && b.teleports == 2 && !b.alive);

    // Departing during another ghost's transfer must be rechecked on lookup.
    bg.AddPlayerToResurrectQueue(50, a.guid);
    bg.AddPlayerToResurrectQueue(50, b.guid);
    a.onTeleport = [&] { ObjectAccessor::players.erase(b.guid); };
    bg.RelocateDeadPlayers(50);
    assert(a.teleports == 3 && b.teleports == 2);
    ObjectAccessor::players.clear();
}
int main() {
    relocationChecks(529); // Arathi Basin.
    relocationChecks(30);  // Alterac Valley uses the same relocation method.
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
    std::puts("BG waves, node-loss relocation, requeue, callbacks and cleanup: OK");
}
'''
with tempfile.TemporaryDirectory(prefix="loa-bg-resurrection-") as directory:
    def run(name, code):
        cpp = Path(directory) / (name + ".cpp")
        exe = Path(directory) / name
        cpp.write_text(code)
        subprocess.run([sys.argv[2], "-std=c++20", "-g", "-D_GLIBCXX_DEBUG", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(cpp), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], capture_output=True, text=True, env=dict(os.environ,
            ASAN_OPTIONS="halt_on_error=1:detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1"))

    result = run("regression", source)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())
    if "--verify-mutations" in sys.argv:
        relocation = body("void Battleground::RelocateDeadPlayers(")
        remove_aura = "player->RemoveAurasDueToSpell(SPELL_WAITING_FOR_RESURRECT);"
        detach = "std::vector<ObjectGuid> ghosts;\n    ghosts.swap(queue->second);\n    m_ReviveQueue.erase(queue);"
        assert remove_aura in relocation and detach in relocation
        for name, replacement, marker in (
            ("stale-aura", relocation.replace(remove_aura, ""), "!waiting && !alive"),
            ("unsafe-iteration", relocation.replace(detach, "std::vector<ObjectGuid>& ghosts = queue->second;"), "singular iterator"),
        ):
            result = run(name, source.replace(relocation, replacement))
            assert result.returncode != 0 and marker in result.stderr, name + ": " + result.stderr
            print("Rejected mutation: " + name)
