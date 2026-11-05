#!/usr/bin/env python3
"""Exercise real BG list builder/handlers with DBC, packet and world doubles.

Checks refusal paths, successful serialization operations, and a mutation that
restores unconditional sending. This is not a client wire-format integration test.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
manager = (root / 'src/server/game/Battlegrounds/BattlegroundMgr.cpp').read_text()
handlers = (root / 'src/server/game/Handlers/BattleGroundHandler.cpp').read_text()


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


builder = function(manager, 'bool BattlegroundMgr::BuildBattlegroundListPacket(')
sender = function(handlers, 'void WorldSession::SendBattleGroundList(')
handler = function(handlers, 'void WorldSession::HandleBattlefieldListOpcode(')
prefix = r'''
#include <cassert>
#include <cstdint>
#include <map>
#include <set>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using BattlegroundTypeId = uint32;
constexpr uint32 SMSG_BATTLEFIELD_LIST = 1, CURRENCY_PRECISION = 100;
enum Config { CONFIG_BG_REWARD_WINNER_CONQUEST_LAST, CONFIG_BG_REWARD_WINNER_CONQUEST_FIRST,
    CONFIG_BG_REWARD_WINNER_HONOR_LAST, CONFIG_BG_REWARD_WINNER_HONOR_FIRST,
    CONFIG_BG_REWARD_LOSER_HONOR_LAST, CONFIG_BG_REWARD_LOSER_HONOR_FIRST };
#define TC_LOG_DEBUG(...) ((void)0)
struct World { int getIntConfig(Config c) { return (int(c) + 1) * 100; } } world;
auto sWorld = &world;
struct Guid {
    uint64_t value = 0;
    static const Guid Empty;
    unsigned operator[](unsigned i) const { return (value >> (i * 8)) & 255; }
    bool operator==(int v) const { return value == uint64_t(v); }
};
const Guid Guid::Empty{};
struct WorldPacket {
    uint32 opcode = 0, request = 3;
    std::vector<uint32> fields;
    unsigned bits = 0, bytes = 0, flushes = 0;
    uint32 count = 0;
    void Initialize(uint32 v) { opcode = v; fields.clear(); }
    WorldPacket& operator<<(uint32 v) { fields.push_back(v); return *this; }
    void operator>>(uint32& v) { v = request; }
    void WriteBit(bool) { ++bits; }
    void WriteBits(uint32 v, unsigned n) { assert(n == 22); count = v; }
    void FlushBits() { ++flushes; }
    void WriteByteSeq(unsigned) { ++bytes; }
};
struct Player {
    unsigned level = 25;
    bool winner = false;
    unsigned GetLevel() { return level; }
    bool GetRandomWinner() { return winner; }
    bool GetBgWeekendWinner() { return false; }
};
struct Battleground { uint32 GetMapId() { return 529; } } battleground;
struct PvPDifficultyEntry {
    uint8 MinLevel = 25, MaxLevel = 29;
    uint32 GetBracketId() const { return 3; }
};
struct DBCManager {
    PvPDifficultyEntry bracket;
    PvPDifficultyEntry const* GetBattlegroundBracketByLevel(uint32 map, uint32 level) {
        assert(map == 529);
        return level >= bracket.MinLevel && level <= bracket.MaxLevel ? &bracket : nullptr;
    }
} sDBCManager;
struct BattlemasterListEntry {};
struct Store {
    BattlemasterListEntry entry;
    BattlemasterListEntry const* LookupEntry(uint32 id) { return id == 3 ? &entry : nullptr; }
} sBattlemasterListStore;
using BattlegroundClientIdsContainer = std::set<uint32>;
struct BGData {
    std::map<uint32, Battleground*> m_Battlegrounds;
    std::map<uint32, BattlegroundClientIdsContainer> m_ClientBattlegroundIds;
};
using BattlegroundDataContainer = std::map<uint32, BGData>;
struct BattlegroundMgr {
    BattlegroundDataContainer bgDataStore;
    bool IsBGWeekend(uint32) { return false; }
    bool BuildBattlegroundListPacket(WorldPacket*, Guid, Player*, BattlegroundTypeId);
} manager;
auto sBattlegroundMgr = &manager;
struct WorldSession {
    Player* _player;
    unsigned sent = 0;
    WorldPacket last;
    void SendPacket(WorldPacket* packet) {
        assert(packet->opcode == SMSG_BATTLEFIELD_LIST);
        assert(!packet->fields.empty());
        ++sent; last = *packet;
    }
    void SendBattleGroundList(Guid, BattlegroundTypeId);
    void HandleBattlefieldListOpcode(WorldPacket&);
};
'''
# The actual ObjectGuid implementation is unrelated to the failure paths.
methods = (builder + '\n' + sender + '\n' + handler).replace('ObjectGuid', 'Guid')
main = r'''
int main() {
    Player player;
    WorldSession session{&player};
    WorldPacket request;
    WorldPacket untouched;
    assert(!manager.BuildBattlegroundListPacket(&untouched, {}, nullptr, 3));
    assert(!untouched.opcode && untouched.fields.empty());
    // Missing BG data, then an empty template container: neither may send.
    session.HandleBattlefieldListOpcode(request);
    session.SendBattleGroundList({17}, 3);
    manager.bgDataStore[3];
    session.HandleBattlefieldListOpcode(request);
    session.SendBattleGroundList({17}, 3);
    assert(session.sent == 0);
    manager.bgDataStore[3].m_Battlegrounds[0] = &battleground;
    for (unsigned level : {1u, 24u, 30u, 90u}) {
        player.level = level;
        session.HandleBattlefieldListOpcode(request);
        session.SendBattleGroundList({17}, 3);
    }
    assert(session.sent == 0);
    assert(manager.bgDataStore[3].m_ClientBattlegroundIds.empty());
    // An eligible bracket with zero instances is still a valid list reply.
    for (unsigned level : {25u, 29u}) {
        player.level = level;
        for (bool won : {false, true}) {
            player.winner = won;
            session.HandleBattlefieldListOpcode(request);
            auto const& out = session.last;
            assert(out.fields == std::vector<uint32>({won ? 1u : 2u, won ? 5u : 6u,
                25u, won ? 1u : 2u, won ? 3u : 4u, 3u, won ? 3u : 4u, 29u, won ? 5u : 6u}));
            assert(out.bits == 12 && out.bytes == 8 && out.flushes == 1 && out.count == 0);
        }
    }
    assert(session.sent == 4);
    manager.bgDataStore[3].m_ClientBattlegroundIds[3] = {11, 22};
    session.SendBattleGroundList({0x1234}, 3);
    assert(session.sent == 5 && session.last.count == 2);
    assert(session.last.fields.size() == 11);
    assert(session.last.fields[9] == 11 && session.last.fields[10] == 22);
    request.request = 999;
    session.HandleBattlefieldListOpcode(request);
    assert(session.sent == 5);
}
'''
with tempfile.TemporaryDirectory(prefix='loa-bg-list-') as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
    for mutation in (False, True):
        code = methods
        if mutation:
            guarded = 'if (sBattlegroundMgr->BuildBattlegroundListPacket(&data, guid, _player, bgTypeId))'
            assert guarded in code
            code = code.replace(guarded, 'sBattlegroundMgr->BuildBattlegroundListPacket(&data, guid, _player, bgTypeId);')
        cpp.write_text(prefix + code + main)
        subprocess.run([sys.argv[2], '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', str(cpp), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True)
        if mutation:
            assert result.returncode != 0 and 'packet->opcode == SMSG_BATTLEFIELD_LIST' in result.stderr, result.stderr
        else:
            assert result.returncode == 0, result.stderr
print('PASS: BG list refusal/success paths, both callers, unconditional-send mutation rejected')
