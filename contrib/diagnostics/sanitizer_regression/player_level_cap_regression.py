#!/usr/bin/env python3
"""Compile production level commands/guards and avoidance lookups with small doubles.

No live player/SQL is changed. Command target resolution, persistence and string
conversion are doubles; cap arithmetic and lookup expressions come from source.
"""
import os
from pathlib import Path
import re
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

commands = (root / "src/server/scripts/Commands/cs_character.cpp").read_text()
player = (root / "src/server/game/Entities/Player/Player.cpp").read_text()
unit = (root / "src/server/game/Entities/Unit/Unit.cpp").read_text()
stats = (root / "src/server/game/Entities/Unit/StatSystem.cpp").read_text()
world = (root / "src/server/game/World/World.cpp").read_text()
enums = (root / "src/server/shared/DataStores/DBCEnums.h").read_text()
cap = re.search(r"DEFAULT_MAX_LEVEL = (\d+)", enums)[1]
assert cap == "90", "MoP player hard cap must stay 90"
levelup = method(commands, "    static bool HandleLevelUpCommand(")
absolute = method(commands, "    static bool HandleCharacterLevelCommand(")
give = method(player, "void Player::GiveLevel(").split("uint8 oldLevel")[0].split("{", 1)[1]
load = player[player.index("    uint8 const storedLevel = fields[6]"):]
load = load[:load.index("    SetUInt32Value(PLAYER_FIELD_XP")]
table = re.search(r"static const float DodgeOrParryPerStat\[90\] =\s*\{.*?\};", stats, re.S)[0]
lookups = [re.search(r"float q = (.*);", method(stats, signature))[1] for signature in (
    "void Player::UpdateDodgePercentage()", "void Player::UpdateParryPercentage()")]
max_config = method(world, "    if (m_int_configs[CONFIG_MAX_PLAYER_LEVEL] < 1")
a = world.index("    if (m_int_configs[CONFIG_START_GM_LEVEL] <")
b = world.index("    m_bool_configs[CONFIG_ALLOW_GM_GROUP]", a)
gm_config = world[a:b]
source = r'''
#include <algorithm>
#include <cassert>
#include <charconv>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <optional>
#include <string>
#include <string_view>
using uint8=uint8_t; using uint32=uint32_t; using int32=int32_t; using int64=int64_t;
constexpr int DEFAULT_MAX_LEVEL=90, STRONG_MAX_LEVEL=255;
constexpr int TYPEID_PLAYER=4, UNIT_FIELD_LEVEL=1, GROUP_UPDATE_FLAG_LEVEL=1;
constexpr int LANG_YOU_CHANGE_LVL=0;
#define TC_LOG_ERROR(...) ((void)0)
using ObjectGuid = uint32;
namespace Trinity {
template<class T> std::optional<T> StringTo(std::string_view s) {
    T value; auto r=std::from_chars(s.data(),s.data()+s.size(),value);
    if(r.ec!=std::errc() || r.ptr!=s.data()+s.size()) return {};
    return value;
}}
struct Player {
    uint8 level=25; static inline uint8 stored=25;
    uint8 GetLevel() const {return level;}
    static uint8 GetLevelFromDB(ObjectGuid) {return stored;}
};
struct Session {Player* GetPlayer() {return nullptr;}};
struct ChatHandler {
    Player* target=nullptr;
    void extractOptFirstArg(char* arg,char** name,char** level) {
        *name=nullptr; *level=*arg ? arg : nullptr;
    }
    bool extractPlayerTarget(char*,Player** p,ObjectGuid*,std::string*) {*p=target;return true;}
    Session* GetSession() {return nullptr;}
    std::string playerLink(std::string const& s) {return s;}
    template<class... T> void PSendSysMessage(T...) {}
};
static uint32 granted=0;
void HandleCharacterLevel(Player* p,ObjectGuid,uint32,uint32 next,ChatHandler*) {
    granted=next; if(p)p->level=next; else Player::stored=next;
}
struct Unit {
    uint32 level=0; int type=TYPEID_PLAYER;
    int GetTypeId() {return type;}
    Unit* ToPlayer() {return this;}
    bool GetGroup() {return false;}
    void SetGroupUpdateFlag(int) {}
    ObjectGuid GetGUID() {return 1;}
    void SetUInt32Value(int,uint32 v) {level=v;}
    void SetLevel(uint8 lvl,bool sendUpdate=true);
};
struct World {void UpdateCharacterNameDataLevel(ObjectGuid,uint8) {}} worldStub;
auto sWorld=&worldStub;
struct Field {uint8 value=0;uint8 GetUInt8(){return value;}};
'''
source += levelup + "\n" + absolute + "\n" + method(unit, "void Unit::SetLevel(")
source += "\nuint8 give(uint8 level) {" + give + "return level;}\n"
source += "uint32 loadedLevel; void SetUInt32Value(int,uint32 v) {loadedLevel=v;}\n"
source += "uint32 load(uint8 level) { Field fields[7]; fields[6].value=level;" + load + "return loadedLevel;}\n"
source += table + "\nuint32 testLevel; uint32 GetLevel(){return testLevel;}\n"
for i, expr in enumerate(lookups):
    source += f"float lookup{i}() {{ return {expr}; }}\n"
source += "enum {CONFIG_MAX_PLAYER_LEVEL,CONFIG_START_GM_LEVEL,CONFIG_START_PLAYER_LEVEL};\n"
source += "uint32 m_int_configs[3]; void checkConfig() {" + max_config + gm_config + "}\n"
source += r'''
bool run(bool absolute, bool offline, uint8 oldLevel, char const* arg) {
    Player p; p.level=oldLevel; Player::stored=oldLevel;
    ChatHandler h; h.target=offline?nullptr:&p; granted=0;
    char input[80]; std::strcpy(input,arg);
    return absolute?HandleCharacterLevelCommand(&h,input):HandleLevelUpCommand(&h,input);
}
int main() {
    testLevel=91;
    assert(lookup0()==DodgeOrParryPerStat[89]);
    assert(lookup1()==DodgeOrParryPerStat[89]);
    for(bool offline : {false,true}) {
        for(uint8 old : {1,25,89,90}) {
            for(auto arg : {"100","+100","2147483647"}) {
                assert(run(false,offline,old,arg)); assert(granted==90);
            }
            for(auto arg : {"-100","-2147483648"}) {
                assert(run(false,offline,old,arg)); assert(granted==1);
            }
            assert(run(true,offline,old,"100")); assert(granted==90);
            assert(run(true,offline,old,"90")); assert(granted==90);
        }
        assert(run(false,offline,90,"")); assert(granted==90);
        assert(run(false,offline,25,"1")); assert(granted==26);
        assert(run(false,offline,90,"-1")); assert(granted==89);
        assert(!run(true,offline,25,"0")); assert(granted==0);
        for(auto bad : {"9999999999999999999999","100junk","+"}) {
            assert(!run(false,offline,25,bad)); assert(granted==0);
            assert(!run(true,offline,25,bad)); assert(granted==0);
        }
    }
    for(unsigned level=0;level<256;++level) {
        auto expected=std::clamp(level,1u,90u);
        assert(give(level)==expected); assert(load(level)==expected);
        Unit u;u.SetLevel(level);assert(u.level==expected);
        u.type=3;u.SetLevel(level);assert(u.level==level); // NPC cap unchanged
        testLevel=level;
        assert(lookup0()==DodgeOrParryPerStat[expected-1]);
        assert(lookup1()==DodgeOrParryPerStat[expected-1]);
    }
    for(unsigned level : {0u,1u,80u,90u,91u,100u,255u,0xffffffffu}) {
        m_int_configs[0]=level;m_int_configs[1]=level;m_int_configs[2]=1;
        checkConfig();
        assert(m_int_configs[0]==((level<1||level>90)?90:level));
        assert(m_int_configs[1]==std::clamp(level,1u,90u));
    }
}
'''
with tempfile.TemporaryDirectory(prefix="loa-level-cap-") as directory:
    path = Path(directory)
    env = os.environ.copy()
    env["ASAN_OPTIONS"] = "halt_on_error=1:detect_leaks=1"
    env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    def compile_run(code, name):
        cpp = path / (name + ".cpp")
        exe = path / name
        cpp.write_text(code)
        subprocess.run([compiler,"-std=c++20","-O1","-g","-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer","-no-pie",str(cpp),"-o",str(exe)],check=True)
        return subprocess.run([str(exe)],env=env,capture_output=True,text=True)
    result = compile_run(source, "fixed")
    assert result.returncode == 0, result.stderr
    # Verify that the regression detects the original out-of-bounds lookup.
    mutation = source.replace(lookups[0], "DodgeOrParryPerStat[GetLevel() - 1]", 1)
    result = compile_run(mutation, "unguarded-lookup")
    assert result.returncode != 0 and ("AddressSanitizer" in result.stderr
                                      or "out of bounds" in result.stderr), result.stderr
    mutation = source.replace("int64(oldlevel) + addlevel, 1, DEFAULT_MAX_LEVEL",
                              "int64(oldlevel) + addlevel, 1, STRONG_MAX_LEVEL", 1)
    result = compile_run(mutation, "old-command-cap")
    assert result.returncode != 0, "Old command cap incorrectly passed"
print("Player level cap: commands, core/login/config guards and both avoidance lookups passed; two mutations rejected")
