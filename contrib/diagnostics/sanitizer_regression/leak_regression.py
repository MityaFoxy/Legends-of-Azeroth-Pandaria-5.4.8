#!/usr/bin/env python3
"""Exercise leak repairs using project declarations/bodies and subsystem doubles.

The complete server's bot-population and shutdown gate remains necessary.
--baseline reads HEAD to demonstrate failure before the uncommitted fixes.
"""

import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
baseline = "--baseline" in sys.argv[3:]


def read(relative):
    if baseline:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "safe.directory=" + str(root),
                "-C",
                str(root),
                "show",
                "HEAD:" + relative,
            ],
            text=True,
        )
    return (root / relative).read_text()


def body(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


script = read("src/server/game/Scripting/ScriptMgr.cpp")
registered = set(
    re.findall(r"ScriptRegistry<(\w+)>::(?:Instance\(\)->)?AddScript\(this\)", script)
)
cleared = set(
    re.findall(r"SCR_CLEAR\((\w+)\)", body(script, "void ScriptMgr::Unload()"))
)
assert registered <= cleared, "Script registries missing shutdown cleanup: " + str(
    registered - cleared
)

maps = read("src/server/game/Maps/Map.cpp")
unload = body(maps, "void Map::UnloadAll()")
assert (
    unload.index("DepopulateMap(this)")
    < unload.index("RemoveAllObjectsInRemoveList()")
    < unload.index("UnloadGrid(")
), "Wild replacements must be deleted before grid unloading"

waypoint_header = read("src/server/game/AI/SmartScripts/SmartScriptMgr.h")
waypoint_cpp = read("src/server/game/AI/SmartScripts/SmartScriptMgr.cpp")
pet_header = read("src/server/game/BattlePet/BattlePetSpawnMgr.h")
pet_cpp = read("src/server/game/BattlePet/BattlePetSpawnMgr.cpp")
mgr_header = read("modules/mod_playerbots/src/Manager/PlayerbotMgr.h")
mgr_cpp = read("modules/mod_playerbots/src/Manager/PlayerbotMgr.cpp")
bot_script = read("modules/mod_playerbots/src/mod_playerbots.cpp")
base_header = read("modules/mod_playerbots/src/AI/PlayerbotAIBase.h")
factory_header = read("modules/mod_playerbots/src/strategy/NamedObjectContext.h")
service_header = read("src/server/game/Services/ServiceMgr.h")
boost_header = read("src/server/game/BattlePay/ServiceBoost.h")
player_cpp = read("src/server/game/Entities/Player/Player.cpp")
add_spell = body(player_cpp, "bool Player::AddSpell(")
learning_begin = add_spell.index("        if (uint32 prev_spell =")
learning_end = add_spell.index(
    "        // replace spells in action bars", learning_begin
)
learning = add_spell[learning_begin:learning_end]

source = (
    r"""
#include <cassert>
#include <cstdint>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>
#include <type_traits>
#include <utility>
using uint8 = std::uint8_t;
using uint16 = std::uint16_t;
using uint32 = std::uint32_t;
using ObjectGuid = uint32;
int waypointCount = 0, petCount = 0, creatureCount = 0, aiCount = 0;
struct WayPoint {
    WayPoint() { ++waypointCount; }
    ~WayPoint() { --waypointCount; }
};
using WPPath = std::unordered_map<uint32, WayPoint*>;
"""
    + body(waypoint_header, "class SmartWaypointMgr").replace("private:", "public:")
    + ";\n"
    + body(waypoint_cpp, "SmartWaypointMgr::~SmartWaypointMgr()")
    + "\n"
    + body(waypoint_cpp, "void SmartWaypointMgr::Clear()")
    + r"""
struct BattlePet {
    BattlePet() { ++petCount; }
    ~BattlePet() { --petCount; }
};
struct CreatureData { uint32 spawntimesecs = 7; };
struct Creature {
    Creature() { ++creatureCount; }
    ~Creature() { --creatureCount; }
    bool queued = false;
    uint32 respawn = 0;
    CreatureData data;
    void AddObjectToRemoveList() { queued = true; }
    void RemoveFromWorld() {}
    CreatureData* GetCreatureData() { return &data; }
    void SetRespawnTime(uint32 time) { respawn = time; }
};
struct Map {
    std::map<ObjectGuid, std::unique_ptr<Creature>> creatures;
    Creature* GetCreature(ObjectGuid guid) {
        auto it = creatures.find(guid);
        return it == creatures.end() ? nullptr : it->second.get();
    }
    void Drain() {
        for (auto it = creatures.begin(); it != creatures.end();)
            if (it->second->queued) it = creatures.erase(it); else ++it;
    }
};
"""
    + pet_header[
        pet_header.index("typedef std::map<ObjectGuid,") : pet_header.index(
            "// handles global spawning"
        )
    ]
    + "\n"
    + body(pet_cpp, "void BattlePetSpawnZoneMgr::RemoveCreature(")
    + "\n"
    + body(pet_cpp, "void BattlePetSpawnZoneMgr::DepopulateZone(")
    + r"""
struct Player { ObjectGuid guid = 10; ObjectGuid GetGUID() const { return guid; } };
class PlayerbotAI;
"""
    + body(base_header, "class PlayerbotAIBase")
    + r""";
PlayerbotAIBase::PlayerbotAIBase(bool isBotAI) : nextAICheckDelay(0), _isBotAI(isBotAI) { ++aiCount; }
void PlayerbotAIBase::UpdateAI(uint32, bool) {}
bool PlayerbotAIBase::IsBotAI() const { return _isBotAI; }
static_assert(std::has_virtual_destructor_v<PlayerbotAIBase>);
struct PlayerbotMgr : PlayerbotAIBase {
    explicit PlayerbotMgr(Player*) : PlayerbotAIBase(false) {}
    ~PlayerbotMgr();
    void OnPlayerLogin(Player*) {}
    void UpdateAIInternal(uint32, bool) override {}
};
"""
)

# The repaired destructor is deliberately defaulted: registry ownership must
# not recursively erase its own entry during unique_ptr destruction.
assert "PlayerbotMgr::~PlayerbotMgr() = default;" in mgr_cpp
source += (
    r"""
PlayerbotMgr::~PlayerbotMgr() { --aiCount; }
struct PlayerbotAI : PlayerbotAIBase {
    explicit PlayerbotAI(Player*) : PlayerbotAIBase(true) {}
    ~PlayerbotAI() { --aiCount; }
    void UpdateAIInternal(uint32, bool) override {}
};
#define ASSERT(x) assert(x)
"""
    + body(mgr_header, "class PlayerbotsMgr").replace("private:", "public:")
    + ";\n"
    + body(mgr_cpp, "void PlayerbotsMgr::AddPlayerbotData(")
    + "\n"
    + body(mgr_cpp, "void PlayerbotsMgr::RemovePlayerBotData(")
    + r"""
PlayerbotsMgr* sPlayerbotsMgr = nullptr;
struct PlayerbotsPlayerScript { void OnLogout(Player* player); };
"""
    + body(bot_script, "void OnLogout(Player* player) override")
    .replace("void OnLogout(", "void PlayerbotsPlayerScript::OnLogout(")
    .replace(" override", "")
    + r"""
struct Qualified { virtual ~Qualified() = default; virtual void Qualify(std::string const&) {} };
"""
    + "template<class T>\n"
    + body(factory_header, "class NamedObjectFactory\n")
    + r""";
static_assert(std::has_virtual_destructor_v<NamedObjectFactory<int>>);
"""
    + body(service_header, "struct RetroactiveFix")
    + r""";
static_assert(std::has_virtual_destructor_v<RetroactiveFix>);
"""
    + body(boost_header, "struct BoostItems")
    + ";\n"
    + re.search(r"typedef std::vector<[^;]+> BoostItemsVector;", boost_header).group()
    + r"""
static_assert(!std::is_pointer_v<BoostItemsVector::value_type>);
struct PlayerSpell {
    PlayerSpell() { ++live; }
    ~PlayerSpell() { --live; }
    static inline int live = 0;
    int state; bool active, dependent, disabled;
};
struct SpellMgr { uint32 GetPrevSpellInChain(uint32 spell) { return spell == 2 ? 1 : 0; } } spellMgr;
auto sSpellMgr = &spellMgr;
struct SpellPlayer {
    std::map<uint32, PlayerSpell*> m_spells;
    int existingUpdates = 0;
    ~SpellPlayer() { for (auto const& [id, spell] : m_spells) delete spell; }
    bool IsInWorld() const { return false; }
    void LearnSpell(uint32 spell, bool dependent) { AddSpell(spell, true, true, dependent, false); }
    bool AddSpell(uint32 spellId, bool active, bool learning, bool dependent, bool disabled, bool loading = false) {
        int state = 1;
        if (auto it = m_spells.find(spellId); it != m_spells.end()) {
            ++existingUpdates;
            it->second->active = active;
            it->second->dependent = dependent;
            it->second->disabled = disabled;
            return false;
        }
        if (spellId == 1) {
            // Simulate SetSkill -> LearnSkillRewardedSpells learning the higher
            // rank while the outer AddSpell is still learning its lower rank.
            m_spells[2] = new PlayerSpell();
            m_spells[2]->active = true;
            return false;
        }
"""
    + learning
    + r"""
        m_spells[spellId] = newspell;
        return true;
    }
};
int main() {
    for (int cycle = 0; cycle < 50; ++cycle) {
        { SmartWaypointMgr mgr;
          for (int id = 1; id <= 3; ++id) {
              auto path = new WPPath;
              for (int wp = 0; wp < 20; ++wp) (*path)[wp] = new WayPoint;
              mgr.waypoint_map[id] = path;
          }
          mgr.Clear(); mgr.Clear(); assert(waypointCount == 0);
          mgr.waypoint_map[99] = new WPPath{{1, new WayPoint}};
        }
        assert(waypointCount == 0);
        { Map map; BattlePetSpawnZoneMgr zone;
          BattlePetSpawnTemplate spawn{};
          map.creatures[1] = std::make_unique<Creature>();
          map.creatures[101] = std::make_unique<Creature>();
          map.creatures[102] = std::make_unique<Creature>();
          // Existing pair, missing original, missing replacement.
          for (int id = 1; id <= 3; ++id) {
              spawn.CreaturesRelation[id] = 100 + id;
              spawn.WildBattlePetInfo[100 + id] = std::make_unique<BattlePet>();
          }
          zone.AddTemplate(std::move(spawn));
          zone.DepopulateZone(&map); zone.DepopulateZone(&map);
          assert(zone.m_spawnTemplates[0].CreaturesRelation.empty());
          assert(zone.m_spawnTemplates[0].WildBattlePetInfo.empty());
          assert(petCount == 0);
          assert(map.GetCreature(1)->respawn == 7);
          assert(map.GetCreature(101)->queued && map.GetCreature(102)->queued);
          map.Drain(); assert(creatureCount == 1);
          zone.m_spawnTemplates[0].WildBattlePetInfo[200] = std::make_unique<BattlePet>();
        }
        assert(petCount == 0 && creatureCount == 0);
        { Player player; PlayerbotsMgr mgr;
          mgr.AddPlayerbotData(&player, true);
          mgr.AddPlayerbotData(&player, true); assert(aiCount == 1);
          mgr.AddPlayerbotData(&player, false); assert(aiCount == 2);
          mgr.AddPlayerbotData(&player, false); assert(aiCount == 2);
          mgr.RemovePlayerBotData(player.guid, true);
          mgr.RemovePlayerBotData(player.guid, true); assert(aiCount == 1);
          sPlayerbotsMgr = &mgr;
          PlayerbotsPlayerScript{}.OnLogout(&player);
          PlayerbotsPlayerScript{}.OnLogout(&player); assert(aiCount == 0);
          mgr.AddPlayerbotData(&player, true);
        }
        assert(aiCount == 0);
        { SpellPlayer player;
          player.AddSpell(2, false, true, true, false);
          assert(player.existingUpdates == 1 && PlayerSpell::live == 1);
          assert(!player.m_spells[2]->active && player.m_spells[2]->dependent);
        }
        assert(PlayerSpell::live == 0);
    }
}
"""
)

with tempfile.TemporaryDirectory(prefix="loa-leak-regression-") as directory:
    cpp = pathlib.Path(directory) / "leak_regression.cpp"
    executable = pathlib.Path(directory) / "leak_regression"
    cpp.write_text(source)
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-g",
            "-O1",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(cpp),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
print("Project leak lifecycle regression passed")
