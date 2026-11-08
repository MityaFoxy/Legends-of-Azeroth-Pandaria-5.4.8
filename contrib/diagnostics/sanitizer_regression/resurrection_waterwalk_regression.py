#!/usr/bin/env python3
"""Execute native resurrection and water-walk setter; packetOnly is not flag cleanup."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]


def extract(path, signature):
    text = (root / path).read_text()
    begin = text.index(signature)
    end, depth = text.index('{', begin) + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]


resurrect = extract('src/server/game/Entities/Player/Player.cpp', 'void Player::ResurrectPlayer(')
setter = extract('src/server/game/Entities/Unit/Unit.cpp', 'bool Unit::SetWaterWalking(')
source = r'''
#include <cassert>
#include <cstdint>
#include <vector>
using uint32=std::uint32_t; using int32=std::int32_t;
constexpr int MOVEMENTFLAG_WATERWALKING=0x04000000, OTHER_FLAG=1;
constexpr int SPELL_AURA_WATER_WALK=104, ALIVE=0, RACE_NIGHTELF=4;
constexpr int SMSG_DEATH_RELEASE_LOC=1, SMSG_SPLINE_MOVE_SET_WATER_WALK=2,
    SMSG_MOVE_WATER_WALK=3, SMSG_SPLINE_MOVE_SET_LAND_WALK=4, SMSG_MOVE_LAND_WALK=5;
constexpr int PLAYER_FIELD_PLAYER_FLAGS=1, PLAYER_FLAGS_IS_OUT_OF_BOUNDS=2,
    OBJECT_FIELD_DYNAMIC_FLAGS=3, UNIT_DYNFLAG_REFER_A_FRIEND=4, CONFIG_DEATH_SICKNESS_LEVEL=5;
constexpr int POWER_MANA=0,POWER_RAGE=1,POWER_ENERGY=2,POWER_FOCUS=3,POWER_ECLIPSE=4,MINUTE=60,IN_MILLISECONDS=1000;
enum class AnimTier { Ground };
struct WorldPacket { WorldPacket(int,int) {} template<class T> WorldPacket& operator<<(T) {return *this;} };
struct Session {
    void SendPacket(WorldPacket*) {}
    bool IsARecruiter() {return false;} uint32 GetRecruiterId() {return 0;}
};
struct Unit {
    int flags=OTHER_FLAG;
    std::vector<int> movementPackets;
    bool HasUnitMovementFlag(int f) const {return flags&f;}
    void AddUnitMovementFlag(int f) {flags|=f;}
    void RemoveUnitMovementFlag(int f) {flags&=~f;}
    bool SetWaterWalking(bool,bool=false);
};
namespace Movement {
struct PacketSender {
    Unit* unit; int opcode;
    PacketSender(Unit* u,int,int op):unit(u),opcode(op) {}
    void Send() {unit->movementPackets.push_back(opcode);}
};
}
struct Aura {void SetDuration(int) {}};
struct Battleground {void HandlePlayerResurrect(void*) {}};
struct World {int getIntConfig(int) {return 11;}} world;
World* sWorld=&world;
struct Outdoor {void HandlePlayerResurrects(void*,uint32) {}} outdoor;
Outdoor* sOutdoorPvPMgr=&outdoor;
constexpr int UNIT_STATE_STUNNED=8;
struct Player:Unit {
    Session session; bool alive=false,ghost=true,waterAura=false;
    int m_deathTimer=100,health=0;
    Session* GetSession() {return &session;}
    void SetAnimTier(AnimTier) {} void RemoveFlag(int,int) {} void SetFlag(int,int) {}
    int GetRace() const {return 1;} int GetLevel() const {return 80;}
    void RemoveAurasDueToSpell(int spell) {if(spell==8326) ghost=false;}
    bool HasAuraType(int type) const {assert(type==SPELL_AURA_WATER_WALK); return waterAura;}
    void setDeathState(int state) {assert(state==ALIVE); alive=true;}
    bool HasUnitState(int) const {return false;} void SetRooted(bool) {}
    void SetHealth(uint32 value) {health=value;} uint32 GetMaxHealth() const {return 100;}
    void SetPower(int,uint32) {} uint32 GetMaxPower(int) const {return 100;}
    void GetZoneAndAreaId(uint32& z,uint32& a) {z=a=1;} void UpdateZone(uint32,uint32) {}
    bool InBattleground() const {return false;} Battleground* GetBattleground() {return nullptr;}
    void UpdateObjectVisibility() {} void UpdatePromotionAuras() {}
    void CastSpell(Player*,int,bool) {} Aura* GetAura(int,int) {return nullptr;} int GetGUID() const {return 7;}
    void ResurrectPlayer(float,bool);
};
''' + setter + resurrect + r'''
int main() {
    // Initial flag is the actual state created by ghost login/BuildPlayerRepop.
    for(bool initialFlag:{true,false}) for(bool hasAura:{false,true}) {
        Player p; p.waterAura=hasAura;
        if(initialFlag) p.AddUnitMovementFlag(MOVEMENTFLAG_WATERWALKING);
        p.ResurrectPlayer(1.f,false);
        assert(p.alive && !p.ghost && p.health==100 && p.m_deathTimer==0);
        assert(p.HasUnitMovementFlag(MOVEMENTFLAG_WATERWALKING)==hasAura);
        assert(p.HasUnitMovementFlag(OTHER_FLAG));
        for(int packet:p.movementPackets)
            assert(packet==(hasAura?SMSG_MOVE_WATER_WALK:SMSG_MOVE_LAND_WALK));
        p.ResurrectPlayer(1.f,false);
        assert(p.HasUnitMovementFlag(MOVEMENTFLAG_WATERWALKING)==hasAura);
    }
    // Do not "fix" packetOnly globally: visibility updates depend on this mode.
    Unit unit; unit.AddUnitMovementFlag(MOVEMENTFLAG_WATERWALKING);
    unit.SetWaterWalking(false,true);
    assert(unit.HasUnitMovementFlag(MOVEMENTFLAG_WATERWALKING));
    unit.SetWaterWalking(false);
    assert(!unit.HasUnitMovementFlag(MOVEMENTFLAG_WATERWALKING));
}
'''
env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-resurrection-waterwalk-') as temporary:
    binary = str(Path(temporary)/'test')
    def run(text):
        subprocess.run([compiler,'-std=c++20','-O1','-g','-no-pie','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-x','c++','-','-o',binary], input=text,text=True,check=True)
        return subprocess.run([binary],env=env,capture_output=True,text=True)
    result = run(source)
    assert result.returncode == 0, result.stderr
    print('Native resurrection water-walk state: passed under ASan/UBSan', flush=True)
    if '--verify-mutations' in sys.argv:
        wanted = 'SetWaterWalking(HasAuraType(SPELL_AURA_WATER_WALK));'
        assert wanted in source
        for broken in ('SetWaterWalking(false, true);', 'SetWaterWalking(false);',
                       'SetWaterWalking(HasAuraType(SPELL_AURA_WATER_WALK), true);'):
            result = run(source.replace(wanted, broken))
            assert result.returncode != 0, 'Mutation escaped: '+broken
            print('Mutation rejected:',broken,flush=True)
