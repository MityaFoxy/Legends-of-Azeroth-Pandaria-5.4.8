#!/usr/bin/env python3
"""Exercise actual auction expiry and copied-target ownership code under LSan."""

import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


auction = (root / "src/server/game/BlackMarket/BlackMarketMgr.cpp").read_text()
smart = (root / "src/server/game/AI/SmartScripts/SmartScript.cpp").read_text()
header = (root / "src/server/game/AI/SmartScripts/SmartScript.h").read_text()
start_path = body(smart, "case SMART_ACTION_WP_START:")
begin = start_path.index("            std::unique_ptr<ObjectList> targets")
end = start_path.index("            me->SetReactState", begin)
owned_targets = start_path[begin:end]
assert "StoreTargetList(new ObjectList" not in smart

source = (
    r"""
#include <cassert>
#include <cstdint>
#include <ctime>
#include <list>
#include <map>
#include <memory>
#include <vector>
using uint32 = std::uint32_t;
using int32 = std::int32_t;
using CharacterDatabaseTransaction = int;
int liveAuctions = 0, won = 0, deletedRows = 0, commits = 0;
struct BlackMarketAuction {
    uint32 id;
    bool expired, bidder;
    bool dbDeleted = false;
    BlackMarketAuction(uint32 id, bool expired, bool bidder) : id(id), expired(expired), bidder(bidder) { ++liveAuctions; }
    ~BlackMarketAuction() { --liveAuctions; }
    bool IsExpired() const { return expired; }
    uint32 GetCurrentBidder() const { return bidder ? 1 : 0; }
    void DeleteFromDB(int) { assert(expired && !dbDeleted); dbDeleted = true; ++deletedRows; }
};
struct Database {
    int BeginTransaction() { return 1; }
    void CommitTransaction(int) { ++commits; }
} CharacterDatabase;
constexpr int CONFIG_BLACK_MARKET_MAX_AUCTIONS = 0;
struct World { int GetIntConfigUnused(); int getIntConfig(int) { return 0; } } world;
auto sWorld = &world;
struct BlackMarketMgr {
    std::map<uint32, BlackMarketAuction*> _auctions;
    uint32 _lastUpdate = 0;
    void Update();
    void SendAuctionWon(BlackMarketAuction* auction, int) { assert(auction->expired && !auction->dbDeleted); ++won; }
    void CreateAuctions(int, int) { assert(false); }
    ~BlackMarketMgr() { for (auto const& [id, auction] : _auctions) delete auction; }
};
"""
    + body(auction, "void BlackMarketMgr::Update()")
    + r"""
using ObjectGuid = uint32;
struct WorldObject { uint32 id; ObjectGuid GetGUID() const { return id; } };
using Unit = WorldObject;
using ObjectList = std::list<WorldObject*>;
using GuidList = std::list<ObjectGuid>;
constexpr uint32 SMART_ESCORT_TARGETS = 1;
struct SmartScript {
    std::map<uint32, GuidList> storage;
    std::map<uint32, GuidList>* mTargetStorage = &storage;
    ObjectList input;
    bool nullInput = false;
    int e = 0;
    ObjectList* GetTargets(int, Unit*) { return nullInput ? nullptr : new ObjectList(input); }
"""
    + body(header, "void StoreTargetList(")
    + r"""
    void StartEscort(Unit* unit) {
"""
    + owned_targets
    + r"""
    }
};
int main() {
    for (int cycle = 0; cycle < 1000; ++cycle) {
        won = deletedRows = commits = 0;
        { BlackMarketMgr mgr;
          for (uint32 id = 1; id <= 5; ++id)
              mgr._auctions[id] = new BlackMarketAuction(id, id % 2 == 1, id != 3);
          mgr.Update();
          assert(won == 2 && deletedRows == 3 && commits == 1);
          assert(liveAuctions == 2 && mgr._auctions.size() == 2);
          assert(mgr._auctions.count(2) && mgr._auctions.count(4) && mgr._lastUpdate);
          mgr.Update(); assert(won == 2 && deletedRows == 3 && liveAuctions == 2 && commits == 2);
        }
        assert(liveAuctions == 0);
        WorldObject first{10}, second{20};
        SmartScript script, receiver;
        script.input = {&first, nullptr, &second, &first};
        script.StartEscort(&first);
        assert((script.storage[SMART_ESCORT_TARGETS] == GuidList{10, 20, 10}));
        script.nullInput = true;
        script.StartEscort(&first);
        assert((script.storage[SMART_ESCORT_TARGETS] == GuidList{10, 20, 10}));
        { auto targets = std::make_unique<ObjectList>(script.input);
          receiver.StoreTargetList(targets.get(), 2);
          receiver.StoreTargetList(targets.get(), 3);
        }
        assert((receiver.storage[2] == GuidList{10, 20, 10}));
        assert(receiver.storage[2] == receiver.storage[3]);
        assert(first.id == 10 && second.id == 20);
    }
}
"""
)
with tempfile.TemporaryDirectory(prefix="loa-auction-target-regression-") as directory:
    cpp = pathlib.Path(directory) / "regression.cpp"
    executable = pathlib.Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(cpp),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
print("Auction expiry and target storage ownership regression passed")
