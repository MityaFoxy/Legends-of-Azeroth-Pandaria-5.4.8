#!/usr/bin/env python3
"""Exercise actual combat/removal bodies with doubles, including callback reentry."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
def body(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

def strip_includes(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#include'))

header = strip_includes((root / 'src/server/game/Combat/CombatManager.h').read_text())
implementation = strip_includes((root / 'src/server/game/Combat/CombatManager.cpp').read_text())
unit = (root / 'src/server/game/Entities/Unit/Unit.cpp').read_text()
prefix = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <unordered_map>
#include <functional>
#include <list>
#include <set>
using uint32=std::uint32_t; using ObjectGuid=uint32;
#define TC_GAME_API
#define ASSERT(c,...) assert(c)
constexpr uint32 IN_MILLISECONDS=1000, TYPEID_PLAYER=1, TYPEID_UNIT=2,
    UNIT_STATE_EVADE=1, UNIT_STATE_IN_FLIGHT=2, UNIT_FIELD_FLAGS=0, UNIT_FLAG_IN_COMBAT=4;
namespace Trinity::Containers {
template<class M, class K> auto MapGetValuePtr(M const& m, K const& k) -> typename M::mapped_type {
    auto p=m.find(k); return p==m.end()?nullptr:p->second;
}}
class Unit;
struct UnitAI {
    std::function<void()> exit, despawn;
    void JustEnteredCombat(Unit*){}
    void JustExitedCombat(){if(exit)exit();}
    void OnDespawn(){if(despawn)despawn();}
};
struct WorldObject {bool inWorld=true; void RemoveFromWorld(){inWorld=false;}};
#define TC_LOG_FATAL(...) ((void)0)
struct EmptyGuid {bool IsEmpty() const {return true;}};
struct Player {bool IsGameMaster() const {return false;} void SendAttackSwingCancelAttack(){}};
struct ThreatManager {void ClearThreat(class Unit*){} void RemoveMeFromThreatLists(){} void ClearAllThreat(){}};
struct Events {void KillAllEvents(bool){}};
struct Motion {void Clear(bool){}};
'''
stub = r'''
class Unit : public WorldObject {
public:
    ObjectGuid guid;
    bool combat=false, controlled=true, m_cleanupDone=false, m_duringRemoveFromWorld=false;
    std::list<Unit*> m_summons;
    std::set<Unit*> m_Controlled;
    UnitAI ai;
    CombatManager m_CombatManager;
    ThreatManager threat;
    Events m_Events;
    Motion motion;
    explicit Unit(ObjectGuid id):guid(id),m_CombatManager(this){}
    bool IsInWorld() const {return inWorld;}
    bool IsAlive() const {return true;}
    void* GetMap() const {return (void*)1;}
    bool InSamePhase(Unit const*) const {return true;}
    bool HasUnitState(uint32) const {return false;}
    bool IsCombatDisallowed() const {return false;}
    bool IsFriendlyTo(Unit const*) const {return false;}
    Player const* GetCharmerOrOwnerPlayerOrPlayerItself() const {return nullptr;}
    bool IsControlledByPlayer() const {return controlled;}
    bool IsImmuneToPC() const {return false;}
    bool IsImmuneToNPC() const {return false;}
    bool IsWithinDistInMap(Unit const*,float) const {return true;}
    ObjectGuid GetGUID() const {return guid;}
    ThreatManager& GetThreatManager(){return threat;}
    CombatManager& GetCombatManager(){return m_CombatManager;}
    CombatManager const& GetCombatManager() const {return m_CombatManager;}
    uint32 GetTypeId() const {return TYPEID_UNIT;}
    bool IsInCombat() const {return combat;}
    void SetInCombatState(bool){combat=true;}
    void RemoveFlag(uint32,uint32){combat=false;}
    UnitAI* GetAI(){return &ai;}
    bool IsNonMeleeSpellCasted(bool){return false;}
    void InterruptNonMeleeSpells(bool){}
    void AttackStop(){}
    void RemoveAllAttackers(){}
    Player* ToPlayer(){return nullptr;}
    void ClearInCombat(){combat=false;}
    void RemoveFromWorld();
    bool IsVehicle(){return false;}
    void RemoveVehicleKit(bool){}
    void RemoveCharmAuras(){}
    void RemoveBindSightAuras(){}
    void RemoveBoundAuras(){}
    void RemoveAllDynObjects(){}
    void RemoveAllAreasTrigger(){}
    void ExitVehicle(){}
    void UnsummonAllTotems(){}
    void RemoveAllControlled(){}
    void RemoveAreaAurasDueToLeaveWorld(){}
    EmptyGuid GetCharmerGUID(){return {};}
    Unit* GetOwner(){return nullptr;}
    uint32 GetEntry(){return 0;}
    void UnSummon(){}
    void RemoveAllAuras(){}
    void RemoveAllGameObjects(){}
    void ClearComboPointHolders(){}
    Motion* GetMotionMaster(){return &motion;}
    void CombatStop(bool includingCast);
    void CleanupBeforeRemoveFromMap(bool finalCleanup);
};
'''
main = r'''
void assertClean(Unit& a, Unit& b) {
    assert(a.GetCombatManager().GetPvPCombatRefs().empty());
    assert(b.GetCombatManager().GetPvPCombatRefs().empty());
    assert(a.GetCombatManager().GetPvECombatRefs().empty());
    assert(b.GetCombatManager().GetPvECombatRefs().empty());
}
int main(){
    { // Real removal ends both PvP and PvE references before deletion.
        Unit guardian(5), opponent(9), npc(10);npc.controlled=false;
        assert(guardian.GetCombatManager().SetInCombatWith(&opponent));
        assert(guardian.GetCombatManager().SetInCombatWith(&npc));
        guardian.RemoveFromWorld();
        assert(!guardian.inWorld && !guardian.m_duringRemoveFromWorld);
        assertClean(guardian,opponent);assertClean(guardian,npc);
        guardian.RemoveFromWorld(); // Idempotent removal and final cleanup.
        guardian.CleanupBeforeRemoveFromMap(true);
        guardian.CleanupBeforeRemoveFromMap(true);
        assert(guardian.m_cleanupDone);assertClean(guardian,opponent);
    }
    { // Already-out-of-world objects must also release retained references.
        Unit a(20),b(21);
        assert(a.GetCombatManager().SetInCombatWith(&b));
        a.inWorld=false;
        a.CleanupBeforeRemoveFromMap(false);
        assert(!a.m_cleanupDone);assertClean(a,b);
        a.CleanupBeforeRemoveFromMap(true);assert(a.m_cleanupDone);
    }
    { // Preserve ordinary temporary combat suppression and later refresh.
        Unit a(30),b(31);
        assert(a.GetCombatManager().SetInCombatWith(&b));
        a.CombatStop(true);
        assert(!a.IsInCombat() && b.IsInCombat());
        assert(a.GetCombatManager().GetPvPCombatRefs().size()==1);
        assert(b.GetCombatManager().GetPvPCombatRefs().size()==1);
        assert(a.GetCombatManager().SetInCombatWith(&b));
        assert(a.IsInCombat());
        a.RemoveFromWorld();assertClean(a,b);
    }
    { // OnDespawn can add refs while still in-world. Exit AI cannot add them back.
        Unit a(40),b(41),c(42);
        int exits=0;
        assert(a.GetCombatManager().SetInCombatWith(&b));
        a.ai.despawn=[&]{assert(a.IsInWorld());assert(a.GetCombatManager().SetInCombatWith(&c));};
        b.ai.exit=[&]{
            ++exits;
            assert(!a.IsInWorld());
            assert(!b.GetCombatManager().SetInCombatWith(&a));
            a.GetCombatManager().EndAllCombat(); // Reentrant symmetric cleanup.
        };
        a.RemoveFromWorld();
        assert(exits==1);assertClean(a,b);assertClean(a,c);
    }
    std::puts("combat removal, bilateral cleanup, callback reentry and suppression: OK");
}
'''
source = prefix + header + stub + implementation + body(unit,'void Unit::CombatStop(bool includingCast)') + body(unit,'void Unit::RemoveFromWorld()') + body(unit,'void Unit::CleanupBeforeRemoveFromMap(bool finalCleanup)') + main
with tempfile.TemporaryDirectory(prefix="loa-combat-removal-") as directory:
    cpp = Path(directory) / "regression.cpp"
    exe = Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
