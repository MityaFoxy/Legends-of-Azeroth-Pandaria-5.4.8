#!/usr/bin/env python3
"""Exercise real BG/Group teardown bodies in both destruction orders under ASan."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])


def body(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


bg = (root / "src/server/game/Battlegrounds/Battleground.cpp").read_text()
group = (root / "src/server/game/Groups/Group.cpp").read_text()
manager = (root / "src/server/game/Groups/GroupMgr.cpp").read_text()
source = r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <list>
#include <map>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
constexpr uint32 ALLIANCE = 469, HORDE = 67, TEAM_ALLIANCE = 0, TEAM_HORDE = 1;
constexpr uint8 MAX_DIFFICULTY = 4;
#define TC_LOG_DEBUG(...) ((void)0)
#define TC_LOG_ERROR(...) assert(false)
int rollsDeleted = 0, scoresDeleted = 0, savesUnbound = 0;
bool cleanupSawLinkedGroup = false;
struct Battleground;
struct Roll { ~Roll() { ++rollsDeleted; } };
struct Save { void RemoveGroup(void*) { ++savesUnbound; } };
struct Binding { Save* save; };
struct Group {
    Battleground* m_bgGroup = nullptr;
    using Rolls = std::list<Roll*>;
    Rolls RollId;
    using BoundInstancesMap = std::map<int, Binding>;
    BoundInstancesMap m_boundInstances[MAX_DIFFICULTY];
    uint8* m_subGroupsCounts = nullptr;
    void SetBattlegroundGroup(Battleground* bg);
    ~Group();
};
struct Score { ~Score() { ++scoresDeleted; } };
struct Map {
    bool unloading = false;
    Battleground* bg = nullptr;
    void SetUnload() { unloading = true; }
    void SetBG(Battleground* value) { bg = value; }
};
struct Battleground {
    Group* m_BgRaids[2] = {};
    std::vector<int> BgCreatures, BgObjects;
    using BattlegroundScoreMap = std::map<int, Score*>;
    BattlegroundScoreMap PlayerScores;
    Map* m_Map = nullptr;
    Group* GetBgRaid(uint32 team) { return m_BgRaids[team == ALLIANCE ? 0 : 1]; }
    void SetBgRaid(uint32 TeamID, Group* bg_raid);
    void DelCreature(uint32) { cleanupSawLinkedGroup |= m_BgRaids[0] || m_BgRaids[1]; }
    void DelObject(uint32) { cleanupSawLinkedGroup |= m_BgRaids[0] || m_BgRaids[1]; }
    int GetTypeID() { return 3; }
    int GetInstanceID() { return 1; }
    void RemoveFromBGFreeSlotQueue() {}
    ~Battleground();
};
struct BGManager { void RemoveBattleground(int, int) {} } bgManager;
auto sBattlegroundMgr = &bgManager;
struct GroupMgr {
    using GroupContainer = std::map<int, Group*>;
    GroupContainer GroupStore;
    ~GroupMgr();
};
'''
source += body(bg, "void Battleground::SetBgRaid(")
source += body(group, "void Group::SetBattlegroundGroup(")
source += body(bg, "Battleground::~Battleground()")
source += body(group, "Group::~Group()")
source += body(manager, "GroupMgr::~GroupMgr()")
source += r'''
int main() {
    { // BG dies first, then the real GroupMgr destructor deletes both raids.
        Map map;
        GroupMgr mgr;
        auto bg = new Battleground;
        map.bg = bg; bg->m_Map = &map;
        bg->BgCreatures = {1}; bg->BgObjects = {1};
        bg->PlayerScores[1] = new Score;
        mgr.GroupStore[1] = new Group;
        mgr.GroupStore[2] = new Group;
        bg->SetBgRaid(ALLIANCE, mgr.GroupStore[1]);
        bg->SetBgRaid(HORDE, mgr.GroupStore[2]);
        delete bg;
        assert(map.unloading && !map.bg);
        // Intentionally let GroupMgr tear down next: old code reproduces UAF.
    }
    assert(!cleanupSawLinkedGroup && scoresDeleted == 1);
    { // Group dies first; its existing destructor unlinks the live BG.
        auto bg = new Battleground;
        auto a = new Group; auto h = new Group;
        bg->SetBgRaid(ALLIANCE, a); bg->SetBgRaid(HORDE, h);
        delete a; assert(!bg->GetBgRaid(ALLIANCE));
        assert(bg->GetBgRaid(HORDE) == h && h->m_bgGroup == bg);
        delete h; assert(!bg->GetBgRaid(HORDE));
        delete bg;
    }
    { // Replacement and repeated detachment keep the other side independent.
        auto bg = new Battleground;
        auto old = new Group; auto replacement = new Group; auto h = new Group;
        bg->SetBgRaid(ALLIANCE, old); bg->SetBgRaid(HORDE, h);
        bg->SetBgRaid(ALLIANCE, replacement);
        assert(!old->m_bgGroup && replacement->m_bgGroup == bg);
        bg->SetBgRaid(ALLIANCE, nullptr); bg->SetBgRaid(ALLIANCE, nullptr);
        assert(!replacement->m_bgGroup && h->m_bgGroup == bg);
        delete bg; assert(!h->m_bgGroup);
        delete old; delete replacement; delete h;
    }
    { // Empty/template BGs and ordinary groups retain existing cleanup.
        delete new Battleground;
        auto g = new Group;
        Save save;
        g->RollId.push_back(new Roll);
        g->m_boundInstances[0][1] = {&save};
        g->m_subGroupsCounts = new uint8[8];
        delete g;
        assert(rollsDeleted == 1 && savesUnbound == 1);
    }
    std::puts("BG/group teardown order, replacement, bilateral unlink and ordinary cleanup: OK");
}
'''
with tempfile.TemporaryDirectory(prefix="loa-bg-group-lifecycle-") as directory:
    cpp = Path(directory) / "regression.cpp"
    exe = Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
