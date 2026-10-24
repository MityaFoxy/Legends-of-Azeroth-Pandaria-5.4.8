#!/usr/bin/env python3
"""Run the real specialization packet handler with bounded player/DBC doubles."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
text = (root / "src/server/game/Handlers/SkillHandler.cpp").read_text()
start = text.index("void WorldSession::HandeSetTalentSpecialization(")
end = text.index("\nvoid WorldSession::HandleLearnTalentOpcode", start)
handler = text[start:end]
source = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <limits>
using uint32 = std::uint32_t;
constexpr uint32 MAX_TALENT_TABS = 4, PLAYER_FIELD_CURRENT_SPEC_ID = 1;
enum Specializations { SPEC_NONE = 0 };
namespace dbc {
std::array<uint32, 4> specs{102, 103, 104, 105};
auto GetClassSpecializations(uint32) { return specs; }
}
struct WorldPacket {
    uint32 tab;
    void operator>>(uint32& value) { value = tab; }
};
struct Session { bool bot = true; bool IsBot() { return bot; } } session;
struct Player {
    uint32 spec = 0, field = 0, updates = 0, learns = 0, pvp = 0, saves = 0;
    uint32 GetClass() { return 11; }
    uint32 GetActiveSpec() { return 0; }
    uint32 GetTalentSpecialization(uint32) { return spec; }
    Session* GetSession() { return &session; }
    void SetTalentSpecialization(uint32, Specializations value) { spec = value; }
    void SetUInt32Value(uint32, uint32 value) { field = value; }
    void SendTalentsInfoData() { ++updates; }
    void LearnSpecializationSpells() { ++learns; }
    void UpdatePvpPower() { ++pvp; }
    void SaveToDB() { ++saves; }
};
struct WorldSession { Player* _player; void HandeSetTalentSpecialization(WorldPacket&); };
'''
source += handler + r'''
int main()
{
    Player player;
    WorldSession server{&player};
    for (uint32 tab : {4u, 5u, std::numeric_limits<uint32>::max()}) {
        WorldPacket packet{tab};
        server.HandeSetTalentSpecialization(packet);
        assert(!player.spec && !player.field && !player.updates && !player.learns && !player.pvp && !player.saves);
    }
    WorldPacket fourth{3};
    server.HandeSetTalentSpecialization(fourth);
    assert(player.spec == 105 && player.field == 105 && player.updates == 1 &&
           player.learns == 1 && player.pvp == 1 && player.saves == 1);
    dbc::specs = {71, 72, 73, 0};
    server.HandeSetTalentSpecialization(fourth);
    assert(player.spec == 105 && player.saves == 1); // empty class slot changes nothing
    session.bot = false;
    WorldPacket first{0};
    server.HandeSetTalentSpecialization(first);
    assert(player.spec == 105 && player.saves == 1); // preserve real-player respec guard
    player.spec = 0;
    server.HandeSetTalentSpecialization(first);
    assert(player.spec == 71 && player.saves == 2);
    session.bot = true;
    WorldPacket second{1};
    server.HandeSetTalentSpecialization(second);
    assert(player.spec == 72 && player.saves == 3);
}
'''
with tempfile.TemporaryDirectory(prefix="loa-spec-packet-") as directory:
    cpp = Path(directory) / "regression.cpp"
    binary = Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="halt_on_error=1:detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1"))
print("PASS: specialization tab bounds, empty slots and native handler side effects")
