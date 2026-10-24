#!/usr/bin/env python3
"""Exercise actual factory/cache bodies with bounded DBC/player doubles.

This is not live character creation, a DBC-file load test, or a guarantee of
thread safety for concurrent player-list mutation/cache rebuilding.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]


def method(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


factory = (root / "modules/mod_playerbots/src/Factory/BotFactory.cpp").read_text()
random_factory = (root / "modules/mod_playerbots/src/Factory/RandomPlayerbotFactory.cpp").read_text()
manager = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotMgr.cpp").read_text()
header = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotMgr.h").read_text()
stores = (root / "src/server/game/DataStores/DBCStores.cpp").read_text()
store_header = (root / "src/server/game/DataStores/DBCStores.h").read_text()
assert "sChrSectionStore" not in stores + store_header + random_factory
assert "sCharSectionsStore" in store_header
assert any("LOAD_DBC(" in line and "sCharSectionsStore" in line and
           '"CharSections.dbc"' in line for line in stores.splitlines())

talents = method(factory, "void BotFactory::InitTalentsTree(bool reset)")
appearance = random_factory[random_factory.index("    std::vector<uint8> skinColors"):
                            random_factory.index("    WorldPacket p;", random_factory.index("    std::vector<uint8> skinColors"))]
cache_methods = "\n".join(method(manager, signature) for signature in (
    "const RandomPlayerbotMgr::city* RandomPlayerbotMgr::GetCityForPlayer(",
    "const RandomPlayerbotMgr::farm_spot* RandomPlayerbotMgr::GetFarmZoneForPlayer("))
cache_types = "\n".join(method(header, "struct " + name) + ";" for name in ("farm_spot", "farm_zone", "city"))
for name in ("GetCityForPlayer", "GetFarmZoneForPlayer"):
    assert name + "(Player* player) const;" in header

prefix = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using Team = uint32;
constexpr Team ALLIANCE = 469, HORDE = 67;
#define TC_LOG_ERROR(...) ((void)0)
#define TC_LOG_DEBUG(...) ((void)0)
#define TC_LOG_WARN(...) ((void)0)
enum Specializations { SPEC_NONE = 0 };
enum { CMSG_SET_PRIMARY_TALENT_TREE = 1, RACE_TAUREN = 6, RACE_DRAENEI = 11,
       RACE_NIGHTELF = 4, RACE_UNDEAD_PLAYER = 5, GENDER_FEMALE = 1,
       SECTION_TYPE_SKIN = 0, SECTION_TYPE_FACE = 1,
       SECTION_TYPE_FACIAL_HAIR = 2, SECTION_TYPE_HAIR = 3 };
thread_local std::mt19937 rng(12345);
thread_local int forcedIndex = -1;
uint32 urand(uint32 low, uint32 high)
{
    assert(low <= high);
    if (forcedIndex >= 0) {
        assert(uint32(forcedIndex) >= low && uint32(forcedIndex) <= high);
        return forcedIndex;
    }
    return std::uniform_int_distribution<uint32>(low, high)(rng);
}
namespace dbc {
    std::array<uint32, 4> specs{};
    auto GetClassSpecializations(uint32) { return specs; }
}
struct WorldPacket {
    uint32 tab = 99;
    explicit WorldPacket(int) {}
    void operator<<(uint32 value) { tab = value; }
};
struct Session {
    std::vector<uint32> tabs;
    void HandeSetTalentSpecialization(WorldPacket& packet) { tabs.push_back(packet.tab); }
};
struct Player {
    uint32 level = 20, spec = 0, cls = 11, zone = 42, team = ALLIANCE;
    bool inWorld = true, teleporting = false;
    Session session;
    uint32 GetLevel() const { return level; }
    uint32 GetClass() const { return cls; }
    uint32 GetSpecialization() const { return spec; }
    uint32 GetTeam() const { return team; }
    uint32 GetZoneId() const { return zone; }
    bool IsInWorld() const { return inWorld; }
    bool IsBeingTeleported() const { return teleporting; }
    std::string GetName() const { return "test bot"; }
    void ResetTalents(bool, bool, bool) { spec = 0; }
    void ActivateSpec(uint32) {}
    Session* GetSession() { return &session; }
    uint32 CalculateTalentsPoints() const { return 0; }
    uint32 GetActiveSpec() const { return 0; }
    bool HasTalent(uint32, uint32) const { return false; }
    bool LearnTalent(uint32) { return true; }
    void SendTalentsInfoData() {}
};
struct TalentEntry { uint32 ID, PlayerClass, TierID, SpellID; };
std::vector<TalentEntry const*> sTalentStore;
struct BotFactory { Player* bot; void InitTalentsTree(bool reset); };
struct CharSectionsEntry { uint32 RaceID, SexID, BaseSection, VariationIndex, ColorIndex; };
struct SectionsStore {
    std::vector<CharSectionsEntry const*> rows;
    uint32 GetNumRows() const { return rows.size(); }
    CharSectionsEntry const* LookupEntry(uint32 id) const { return rows.at(id); }
} sCharSectionsStore;
struct Appearance { uint8 skin, face, hair, hairColor, facialHair; } chosen;
Player appearancePlayer;
using PlayerBotMap = std::map<uint32, Player*>;
'''

declarations = r'''
    std::vector<city> _city_cache_data;
    std::vector<farm_zone> _farm_cache_data;
    std::vector<Player*> _players;
    PlayerBotMap playerBots;
    auto GetPlayerBotsBegin() const { return playerBots.cbegin(); }
    auto GetPlayerBotsEnd() const { return playerBots.cend(); }
    const city* GetCityForPlayer(Player* player) const;
    const farm_spot* GetFarmZoneForPlayer(Player* player) const;
'''

tests = r'''
void testSpecializations()
{
    Player player;
    BotFactory factory{&player};
    auto checkTabs = [&](std::array<uint32, 4> specs, std::vector<uint32> expected) {
        dbc::specs = specs;
        for (uint32 index = 0; index < expected.size(); ++index) {
            forcedIndex = index;
            player.session.tabs.clear();
            factory.InitTalentsTree(false);
            assert(player.session.tabs == std::vector<uint32>{expected[index]});
        }
    };
    checkTabs({102, 103, 104, 105}, {0, 1, 2, 3}); // druid: fourth is reachable
    player.cls = 1;
    checkTabs({71, 72, 73, 0}, {0, 1, 2});
    checkTabs({71, 0, 73, 0}, {0, 2}); // tab index, not list index or spec ID
    dbc::specs = {};
    player.session.tabs.clear();
    factory.InitTalentsTree(false);
    assert(player.session.tabs.empty()); // no invalid RNG range for empty DBC
    dbc::specs = {71, 72, 73, 0};
    player.level = 9;
    factory.InitTalentsTree(false);
    assert(player.session.tabs.empty());
    player.level = 10;
    player.spec = 71;
    factory.InitTalentsTree(false);
    assert(player.session.tabs.empty());
    forcedIndex = 2;
    factory.InitTalentsTree(true);
    assert(player.session.tabs == std::vector<uint32>{2});
    forcedIndex = -1;
}
void testAppearance()
{
    CharSectionsEntry skin{1, 0, SECTION_TYPE_SKIN, 0, 7};
    CharSectionsEntry face{1, 0, SECTION_TYPE_FACE, 3, 7};
    CharSectionsEntry hair{1, 0, SECTION_TYPE_HAIR, 5, 9};
    CharSectionsEntry facial{1, 0, SECTION_TYPE_FACIAL_HAIR, 2, 0};
    CharSectionsEntry wrongRace{2, 0, SECTION_TYPE_HAIR, 99, 99};
    CharSectionsEntry wrongSex{1, 1, SECTION_TYPE_HAIR, 99, 99};
    sCharSectionsStore.rows = {nullptr, &skin, nullptr, &face, &hair, &facial, &wrongRace, &wrongSex};
    assert(selectAppearance(1, 0));
    assert(chosen.skin == 7 && chosen.face == 3 && chosen.hair == 5 &&
           chosen.hairColor == 9 && chosen.facialHair == 2);
    // Every required category fails closed instead of modulo zero.
    for (uint32 index : {1u, 3u, 4u, 5u}) {
        auto saved = sCharSectionsStore.rows[index];
        sCharSectionsStore.rows[index] = nullptr;
        assert(!selectAppearance(1, 0));
        sCharSectionsStore.rows[index] = saved;
    }
    assert(!selectAppearance(3, 0));
    skin.SexID = face.SexID = hair.SexID = 1;
    sCharSectionsStore.rows = {&skin, &face, &hair};
    assert(selectAppearance(1, 1) && chosen.facialHair == 0);
    skin.RaceID = face.RaceID = hair.RaceID = RACE_NIGHTELF;
    assert(!selectAppearance(RACE_NIGHTELF, 1)); // existing facial-hair policy retained
    sCharSectionsStore.rows.clear();
    assert(!selectAppearance(1, 0));
}
std::string fingerprint(RandomPlayerbotMgr const& mgr)
{
    std::ostringstream out;
    for (auto const& city : mgr._city_cache_data)
        out << city.zone_id << ',' << city.city_id << ',' << city.map_id << ','
            << city.min_level << ',' << city.max_level << ',' << city.team_disabled
            << ',' << city.x << ',' << city.y << ',' << city.z << ';';
    out << '|';
    for (auto const& zone : mgr._farm_cache_data) {
        out << zone.zone_id << ',' << zone.zone_type << ',' << zone.min_level << ','
            << zone.max_level << ',' << zone.team_disabled << ',' << zone.map_id
            << ',' << zone.min_player << ',' << zone.max_player << ':';
        for (auto const& spot : zone.spots)
            out << spot.min_level << ',' << spot.max_level << ',' << spot.map_id
                << ',' << spot.x << ',' << spot.y << ',' << spot.z << ';';
        out << '|';
    }
    return out.str();
}
void testCaches()
{
    RandomPlayerbotMgr mgr;
    Player player;
    assert(!mgr.GetCityForPlayer(nullptr) && !mgr.GetFarmZoneForPlayer(nullptr));
    assert(!mgr.GetCityForPlayer(&player) && !mgr.GetFarmZoneForPlayer(&player));
    mgr._city_cache_data = {{1, 1, 0, 20, 20, HORDE, 1, 2, 3}};
    mgr._farm_cache_data = {{42, 0, 20, 20, HORDE, 0, 0, 1,
        {{20, 20, 0, 4, 5, 6}}}};
    assert(mgr.GetCityForPlayer(&player) == &mgr._city_cache_data[0]);
    assert(mgr.GetFarmZoneForPlayer(&player) == &mgr._farm_cache_data[0].spots[0]);
    for (auto level : {19u, 21u}) {
        player.level = level;
        assert(!mgr.GetCityForPlayer(&player) && !mgr.GetFarmZoneForPlayer(&player));
    }
    player.level = 20;
    player.team = HORDE;
    assert(!mgr.GetCityForPlayer(&player) && !mgr.GetFarmZoneForPlayer(&player));
    player.team = ALLIANCE;
    auto& spot = mgr._farm_cache_data[0].spots[0];
    spot.min_level = 21;
    assert(!mgr.GetFarmZoneForPlayer(&player));
    spot.min_level = 20;
    spot.max_level = 19;
    assert(!mgr.GetFarmZoneForPlayer(&player));
    spot.max_level = 20;
    Player resident;
    mgr._players = {nullptr, &player, &resident};
    assert(!mgr.GetFarmZoneForPlayer(&player));
    resident.inWorld = false;
    assert(mgr.GetFarmZoneForPlayer(&player));
    resident.inWorld = true;
    resident.teleporting = true;
    assert(mgr.GetFarmZoneForPlayer(&player));
    resident.teleporting = false;
    resident.zone = 43;
    assert(mgr.GetFarmZoneForPlayer(&player));
    mgr._players = {nullptr, &player};
    resident.zone = 42;
    mgr.playerBots = {{1, nullptr}, {2, &player}, {3, &resident}};
    assert(!mgr.GetFarmZoneForPlayer(&player));
    resident.teleporting = true;
    assert(mgr.GetFarmZoneForPlayer(&player));
    resident.teleporting = false;
    resident.inWorld = false;
    assert(mgr.GetFarmZoneForPlayer(&player));
    resident.inWorld = true;
    resident.zone = 43;
    assert(mgr.GetFarmZoneForPlayer(&player));
    mgr._farm_cache_data[0].max_player = 0;
    resident.zone = 42;
    assert(mgr.GetFarmZoneForPlayer(&player)); // unlimited capacity

    mgr._city_cache_data.push_back({2, 2, 0, 1, 90, HORDE, 7, 8, 9});
    mgr._farm_cache_data.push_back({43, 0, 1, 90, HORDE, 0, 0, 0,
        {{1, 90, 0, 10, 0, 0}, {1, 90, 0, 11, 0, 0}, {1, 90, 0, 12, 0, 0}}});
    // An eligible zone without eligible spots must not displace a valid result.
    mgr._farm_cache_data.push_back({44, 0, 1, 90, HORDE, 0, 0, 0, {}});
    auto before = fingerprint(mgr);
    auto cityPointer = &mgr._city_cache_data[0];
    auto spotPointer = &mgr._farm_cache_data[0].spots[0];
    uint32 zoneOne = 0, cityOne = 0;
    std::array<uint32, 3> otherSpots{};
    for (int n = 0; n < 20000; ++n) {
        cityOne += mgr.GetCityForPlayer(&player)->city_id == 1;
        auto result = mgr.GetFarmZoneForPlayer(&player);
        assert(result);
        assert(cityPointer->city_id == 1 && spotPointer->x == 4);
        if (result->x == 4) ++zoneOne;
        else { assert(result->x >= 10 && result->x <= 12); ++otherSpots[result->x - 10]; }
    }
    // Equal chance per zone, not 1:3 weighted by its number of spots.
    assert(zoneOne > 9000 && zoneOne < 11000);
    assert(cityOne > 9000 && cityOne < 11000);
    for (auto count : otherSpots) assert(count > 2800 && count < 3900);
    std::vector<std::thread> readers;
    for (uint32 index = 0; index < 8; ++index)
        readers.emplace_back([&, index] {
            rng.seed(500 + index);
            for (int n = 0; n < 2000; ++n) {
                assert(mgr.GetCityForPlayer(&player));
                assert(mgr.GetFarmZoneForPlayer(&player));
            }
        });
    for (auto& reader : readers) reader.join();
    assert(fingerprint(mgr) == before);
    assert(cityPointer == &mgr._city_cache_data[0] && cityPointer->city_id == 1);
    assert(spotPointer == &mgr._farm_cache_data[0].spots[0] && spotPointer->x == 4);
}
int main() { testSpecializations(); testAppearance(); testCaches(); }
'''

source = (prefix + talents + "\nPlayer* selectAppearance(uint8 race, uint8 gender) {\n" +
          appearance + "\nchosen = {face.second, face.first, hair.first, hair.second, facialHair};\n"
          "return &appearancePlayer;\n}\nstruct RandomPlayerbotMgr {\n" + cache_types +
          declarations + "\n};\n" + cache_methods + tests)
with tempfile.TemporaryDirectory(prefix="loa-factory-cache-") as directory:
    cpp = Path(directory) / "regression.cpp"
    binary = Path(directory) / "regression"
    cpp.write_text(source)
    sanitizer = "thread" if "--tsan" in sys.argv[3:] else "address,undefined"
    subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-pthread",
                    "-fsanitize=" + sanitizer, "-fno-omit-frame-pointer",
                    str(cpp), "-o", str(binary)], check=True)
    environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                       UBSAN_OPTIONS="halt_on_error=1", TSAN_OPTIONS="halt_on_error=1")
    subprocess.run([str(binary)], env=environment, check=True)
print("PASS: specialization tabs, loaded appearance store, immutable city/farm selection")
