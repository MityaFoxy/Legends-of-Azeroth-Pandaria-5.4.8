#!/usr/bin/env python3
"""Production travel/adapter against controlled world APIs; no live mmap claim."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"

def without_directives(path):
    return "\n".join(line for line in path.read_text().splitlines() if not line.startswith("#"))

def method(path, signature):
    text = path.read_text()
    begin = text.index(signature)
    brace = text.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin:end]

source = r'''
#include "BotLifeTravel.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
#include <functional>
using uint8 = uint8_t;
using uint32 = uint32_t;
namespace G3D {
struct Vector3 {
    float x=0,y=0,z=0;
    Vector3 operator-(Vector3 const& b) const { return {x-b.x,y-b.y,z-b.z}; }
    float length() const { return std::sqrt(x*x+y*y+z*z); }
};
}
class MovementGenerator {};
''' + without_directives(root / "modules/mod_playerbots/src/strategy/value/GroundMovementState.h") + r'''
enum { IDLE_MOTION_TYPE, POINT_MOTION_TYPE, CHASE_MOTION_TYPE, FOLLOW_MOTION_TYPE };
enum { UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2, UNIT_STATE_LOST_CONTROL=4 };
enum { SPELL_AURA_MOD_INCREASE_MOUNTED_FLIGHT_SPEED=1 };
enum class MovementPriority { MOVEMENT_NORMAL };
struct MotionMaster {
    MovementGenerator point,foreign;
    MovementGenerator* generator=nullptr;
    int type=IDLE_MOTION_TYPE, expired=0;
    MovementGenerator* top() const { return generator; }
    int GetCurrentMovementGeneratorType() const { return type; }
    void MovementExpired() { ++expired; type=IDLE_MOTION_TYPE; generator=nullptr; }
};
struct Spline { uint32 id=1; bool finalized=true;
    uint32 GetId() const { return id; } bool Finalized() const { return finalized; }
};
struct Session { bool logout=false; bool isLogingOut() const { return logout; } };
struct Guid { uint32 GetCounter() const { return 14; } };
struct Player {
    bool inWorld=true,removing=false,alive=true,teleport=false,sessionPresent=true;
    bool bg=false,arena=false,taxi=false,transport=false,vehicle=false,flying=false,flightAura=false;
    bool combat=false,casting=false,allowed=true,los=true;
    uint32 map=0,instance=0,phase=1,state=0;
    float x=0,y=0,z=0;
    int stopped=0;
    MotionMaster motion; Spline spline; Spline* movespline=&spline; Session session;
    bool IsInWorld() const { return inWorld; } bool IsDuringRemoveFromWorld() const { return removing; }
    bool IsAlive() const { return alive; } bool IsBeingTeleported() const { return teleport; }
    Session* GetSession() { return sessionPresent ? &session : nullptr; }
    bool InBattleground() const { return bg; } bool InArena() const { return arena; }
    bool IsInFlight() const { return taxi; } bool GetTransport() const { return transport; }
    bool GetVehicle() const { return vehicle; } bool IsFlying() const { return flying; }
    bool HasAuraType(int) const { return flightAura; }
    uint32 GetMapId() const { assert(inWorld && !removing); return map; }
    uint32 GetInstanceId() const { assert(inWorld && !removing); return instance; }
    uint32 GetPhaseMask() const { assert(inWorld && !removing); return phase; }
    bool IsInCombat() const { return combat; } bool HasUnitState(uint32 mask) const { return state&mask; }
    bool IsNonMeleeSpellCasted(bool) const { return casting; }
    float GetExactDist(float a,float b,float c) const { return G3D::Vector3{x-a,y-b,z-c}.length(); }
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }
    bool IsWithinLOS(float,float,float) const { return los; }
    MotionMaster* GetMotionMaster() { return &motion; } Guid GetGUID() const { return {}; }
    void StopMoving() { ++stopped; spline.finalized=true; ++spline.id; }
};
struct LastMovement {
    GroundMovementState groundMovement;
    int delay=0,clears=0;
    void clear() { groundMovement={}; delay=0; ++clears; }
};
struct PlayerbotAI {
    Player* bot;
    LastMovement last;
    bool real=false,master=false;
    int moveCalls=0, outcome=0;
    float partialEnd=0;
    bool IsRealPlayer() const { return real; } bool HasRealPlayerMaster() const { return master; }
};
namespace Trinity { bool IsValidMapCoord(float x,float y,float z) {
    return std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z)&&std::abs(x)<17000&&std::abs(y)<17000;
} }
class MovementAction {
protected:
    enum class MoveFailure { None, Route, RecoveryExhausted };
    MoveFailure lastMoveFailure=MoveFailure::None;
    PlayerbotAI* botAI; Player* bot;
    MovementAction(PlayerbotAI* ai,std::string) : botAI(ai),bot(ai->bot) {}
    bool IsMovingAllowed() const { return bot->allowed; }
    bool MoveTo(uint32,float x,float y,float z,bool idle,bool react,bool normal,bool exact,MovementPriority) {
        assert(!idle && !react && normal && !exact); ++botAI->moveCalls;
        lastMoveFailure=botAI->outcome==1 ? MoveFailure::Route :
            botAI->outcome==2 ? MoveFailure::RecoveryExhausted : MoveFailure::None;
        if(botAI->outcome) return false;
        auto& state=botAI->last.groundMovement;
        state={}; state.tracked=state.active=true;
        state.mapId=bot->map; state.instanceId=bot->instance;
        state.goal={x,y,z}; state.endpoint={botAI->partialEnd ? botAI->partialEnd : x,y,z};
        bot->motion.generator=&bot->motion.point; bot->motion.type=POINT_MOTION_TYPE;
        state.generator=bot->motion.generator; state.splineId=++bot->spline.id;
        bot->spline.finalized=false; botAI->last.delay=5000;
        return true;
    }
};
#define AI_VALUE(type,name) (botAI->last)
#define TC_LOG_DEBUG(...) do {} while(false)
''' + without_directives(module / "BotLifeMovement.h") + without_directives(module / "BotLifeMovement.cpp") + r'''
#define TC_LOG_ERROR(...) do {} while(false)
#define TC_LOG_WARN(...) do {} while(false)
namespace BotLife {
bool enabled=false;
uint32 botGuid=0;
TravelTarget destination;
bool onlyEligible=true;
bool IsOnlyEligibleBot(uint32 guid) { return onlyEligible && guid==6; }
struct TestConfig {
    bool enable=false; int guid=6; std::string target="1 -8218.48 -4293.23 13.6594";
    bool GetBoolDefault(std::string const& key,bool) { return key.find("QuestRun") == key.npos && enable; }
    int GetIntDefault(char const*,int) { return guid; }
    std::string GetStringDefault(char const*,char const*) { return target; }
} testConfig;
auto* sConfigMgr=&testConfig;
''' + method(module / "BotLifeTravelTest.cpp", "void LoadTravelTestConfig()") + r'''
void configTests() {
    LoadTravelTestConfig(); assert(!enabled);
    testConfig.enable=true; LoadTravelTestConfig(); assert(enabled && botGuid==6 && destination.mapId==1);
    onlyEligible=false; LoadTravelTestConfig(); assert(!enabled); onlyEligible=true;
    for(int guid : {0,9,-1}) { testConfig.guid=guid; LoadTravelTestConfig(); assert(!enabled); }
    testConfig.guid=6;
    for(char const* value : {"", "1 2 3", "1 nan 2 3", "1 999999 2 3", "1 2 3 4 trailing"}) {
        testConfig.target=value; LoadTravelTestConfig(); assert(!enabled);
    }
    testConfig.target="1 2 3 4  "; LoadTravelTestConfig(); assert(enabled);
}
}
using namespace BotLife;
TravelTarget target{0,0,1,100,0,0,1};
struct Scene {
    Player bot; PlayerbotAI ai{&bot}; NativeTravelMovement movement{ai}; TravelExecutor travel{movement};
    void start(TravelLimits limits={}) { travel.Start(target,limits); assert(travel.Update(0)==TravelStatus::Running); }
    void finish(float x) { bot.x=x; bot.spline.finalized=true; bot.motion.type=IDLE_MOTION_TYPE; bot.motion.generator=nullptr; }
    void foreign(int type=CHASE_MOTION_TYPE) { bot.motion.type=type; bot.motion.generator=&bot.motion.foreign;
        ++bot.spline.id; bot.spline.finalized=false; ai.last.delay=777; }
};
int main() {
    // A rejected native route is cancelled while it is still ours, before
    // world movement; the default adapter remains unchanged for other users.
    { Player bot; PlayerbotAI ai{&bot};
      NativeTravelMovement movement(ai, [] { return false; });
      assert(movement.Move({0,0,1,10,0,0,1})==TravelMoveResult::UnsafeRoute);
      assert(!movement.OwnsMovement() && bot.stopped==1 && bot.motion.expired==1); }
    { Player bot; PlayerbotAI ai{&bot}; NativeTravelMovement movement(ai, [] { return false; });
      TravelExecutor travel(movement); travel.Start({0,0,1,10,0,0,1});
      assert(travel.Update(0)==TravelStatus::Failed && travel.GetFailure()==TravelFailure::UnsafeRoute);
      assert(travel.GetAttempts()==1 && travel.GetFailedAttempts()==0);
      for(int i=0;i<10;++i) assert(travel.Update(1000)==TravelStatus::Failed);
      assert(ai.moveCalls==1 && !movement.OwnsMovement() && bot.stopped==1); }
    configTests();
    { Scene s; s.start(); assert(s.travel.ControlsMovement() && s.ai.moveCalls==1);
      for(int i=0;i<10;++i) assert(s.travel.Update(100)==TravelStatus::Running);
      assert(s.ai.moveCalls==1); s.travel.Pause(); s.travel.Pause();
      assert(s.bot.stopped==1 && s.bot.motion.expired==1 && !s.travel.ControlsMovement());
      assert(s.travel.Update(UINT32_MAX)==TravelStatus::Paused && s.travel.Resume());
      assert(s.travel.Update(UINT32_MAX)==TravelStatus::Running && s.ai.moveCalls==2);
      s.bot.x=100; assert(s.travel.Update(1)==TravelStatus::Arrived);
      assert(s.bot.stopped==2 && !s.travel.ControlsMovement());
      s.travel.Update(UINT32_MAX); assert(s.ai.moveCalls==2); }
    // Native recovery may replace BOTH generator and spline without losing owner.
    { Scene s; s.start(); auto owner=s.ai.last.groundMovement.owner;
      s.bot.motion.generator=&s.bot.motion.foreign; ++s.bot.spline.id;
      auto& state=s.ai.last.groundMovement; state.generator=s.bot.motion.generator;
      state.splineId=s.bot.spline.id; state.endpoint={50,0,0};
      assert(s.travel.ControlsMovement()); s.travel.Cancel();
      assert(s.bot.stopped==1 && s.bot.motion.expired==1); }
    // A single native watchdog owns recovery: BotLife observes, never reissues.
    { Scene s; s.start(); auto& state=s.ai.last.groundMovement; state.recovering=true;
      for(int i=0;i<5;++i) assert(s.travel.Update(100)==TravelStatus::Recovering);
      assert(s.travel.ControlsMovement() && s.ai.moveCalls==1 && s.travel.GetAttempts()==1);
      state.recovering=false; assert(s.travel.Update(100)==TravelStatus::Running);
      state.recovering=true; assert(s.travel.Update(100)==TravelStatus::Recovering);
      s.travel.Pause(); assert(s.travel.GetStatus()==TravelStatus::Paused && !s.travel.ControlsMovement());
      assert(s.travel.Resume()); assert(s.travel.Update(UINT32_MAX)==TravelStatus::Running);
      s.travel.Cancel(); assert(!s.travel.ControlsMovement()); }
    { Scene s; s.start(); s.ai.last.groundMovement.recovering=true;
      assert(s.travel.Update(1)==TravelStatus::Recovering);
      s.ai.last.groundMovement.exhausted=true; s.ai.last.groundMovement.active=false;
      s.finish(0); assert(s.travel.Update(1)==TravelStatus::Failed);
      assert(s.travel.GetFailure()==TravelFailure::RecoveryExhausted);
      assert(s.ai.last.groundMovement.exhausted && !s.ai.last.groundMovement.owner);
      s.travel.Update(10000); assert(s.ai.moveCalls==1); }
    { Scene s; s.start({1000,1000,8}); s.ai.last.groundMovement.recovering=true;
      assert(s.travel.Update(100)==TravelStatus::Recovering);
      assert(s.travel.Update(900)==TravelStatus::Failed && s.travel.GetFailure()==TravelFailure::Timeout); }
    { Scene s; s.start(); s.ai.last.groundMovement.recovering=true;
      s.travel.Update(1); s.foreign();
      assert(s.travel.Update(1)==TravelStatus::Failed && !s.bot.stopped && !s.bot.motion.expired); }
    assert(std::string(ToString(TravelStatus::Recovering))=="Recovering");
    assert(std::string(ToString(TravelFailure::RecoveryExhausted))=="RecoveryExhausted");
    for(int type : {CHASE_MOTION_TYPE,FOLLOW_MOTION_TYPE,POINT_MOTION_TYPE}) {
      Scene s; s.start(); s.foreign(type);
      assert(!s.travel.ControlsMovement()); assert(s.travel.Update(10)==TravelStatus::Failed);
      assert(s.travel.GetFailure()==TravelFailure::MovementLost);
      s.travel.Cancel(); assert(!s.bot.stopped && !s.bot.motion.expired && s.ai.last.delay==777);
    }
    // Even identical goal/generator/spline cannot recover a revoked token.
    { Scene s; s.start(); s.ai.last.groundMovement.owner.reset();
      assert(!s.travel.ControlsMovement()); s.travel.Pause(); assert(!s.bot.stopped); }
    // A foreign same-generator spline is not our command either.
    { Scene s; s.start(); ++s.bot.spline.id; s.travel.Cancel(); assert(!s.bot.stopped); }
    // Partial routes aren't arrival; cooldown and bounded replanning to original goal.
    { Scene s; s.ai.partialEnd=40; s.start(); s.finish(40);
      assert(s.travel.Update(1)==TravelStatus::TemporarilyBlocked);
      s.travel.Update(999); assert(s.ai.moveCalls==1); s.travel.Update(1); assert(s.ai.moveCalls==2);
      assert(s.ai.last.groundMovement.goal.x==100); s.finish(100);
      assert(s.travel.Update(1)==TravelStatus::Arrived); }
    { Scene s; s.ai.outcome=1; s.travel.Start(target,{10000,1000,2});
      assert(s.travel.Update(0)==TravelStatus::TemporarilyBlocked);
      s.travel.Update(999); assert(s.ai.moveCalls==1); s.travel.Update(1); assert(s.ai.moveCalls==2);
      assert(s.travel.Update(1000)==TravelStatus::Failed && s.travel.GetFailure()==TravelFailure::AttemptLimit);
      assert(!s.bot.stopped); }
    { Scene s; s.ai.outcome=2; s.travel.Start(target);
      assert(s.travel.Update(0)==TravelStatus::Failed && s.travel.GetFailure()==TravelFailure::RecoveryExhausted); }
    { Scene s; s.start(); s.ai.last.groundMovement.exhausted=true;
      s.finish(0); assert(s.travel.Update(1)==TravelStatus::Failed);
      assert(s.ai.last.groundMovement.exhausted && !s.bot.stopped); }
    { Scene s; s.start({1000,1000,8});
      assert(s.travel.Update(UINT32_MAX)==TravelStatus::Failed && s.travel.GetFailure()==TravelFailure::Timeout);
      assert(s.bot.stopped==1); }
    for(int flag : {UNIT_STATE_ROOT,UNIT_STATE_STUNNED,UNIT_STATE_LOST_CONTROL}) {
      Scene s; s.bot.state=flag; s.travel.Start(target);
      assert(s.travel.Update(0)==TravelStatus::TemporarilyBlocked && s.ai.moveCalls==0);
      s.bot.state=0; assert(s.travel.Update(100)==TravelStatus::Running); s.travel.Cancel(); }
    { Scene s; s.bot.casting=true; s.travel.Start(target,{1000,1000,8});
      s.travel.Update(0); assert(s.travel.GetAttempts()==0 && !s.travel.ControlsMovement());
      assert(s.travel.Update(1000)==TravelStatus::Failed); }
    // Never replace pre-existing native motion, including an untracked spline.
    { Scene s; s.foreign(); s.travel.Start(target); s.travel.Update(0);
      assert(!s.ai.moveCalls && !s.bot.stopped && !s.travel.ControlsMovement()); }
    { Scene s; s.bot.spline.finalized=false; s.travel.Start(target); s.travel.Update(0);
      assert(!s.ai.moveCalls && !s.bot.stopped); }
    // Arrival requires 3D range AND LOS; no quest interaction is performed.
    { Scene s; s.bot.x=100; s.bot.z=4; assert(!s.movement.HasArrived(target));
      s.bot.z=0; s.bot.los=false; assert(!s.movement.HasArrived(target));
      s.bot.los=true; s.travel.Start(target); assert(s.travel.Update(0)==TravelStatus::Arrived && !s.ai.moveCalls); }
    for(int mode=0;mode<18;++mode) {
      Scene s; s.start(); s.travel.Pause();
      switch(mode) {
        case 0:s.bot.inWorld=false;break; case 1:s.bot.removing=true;break;
        case 2:s.bot.alive=false;break; case 3:s.bot.teleport=true;break;
        case 4:s.bot.sessionPresent=false;break; case 5:s.bot.session.logout=true;break;
        case 6:s.ai.real=true;break; case 7:s.ai.master=true;break;
        case 8:s.bot.bg=true;break; case 9:s.bot.arena=true;break;
        case 10:s.bot.taxi=true;break; case 11:s.bot.transport=true;break;
        case 12:s.bot.vehicle=true;break; case 13:s.bot.flying=true;break;
        case 14:++s.bot.map;break; case 15:++s.bot.instance;break;
        case 16:++s.bot.phase;break; case 17:s.bot.flightAura=true;break;
      }
      assert(!s.travel.Resume() && s.travel.GetFailure()==TravelFailure::InvalidTarget);
      assert(s.ai.moveCalls==1 && s.bot.stopped==1);
    }
    { Scene s; s.start(); s.bot.inWorld=false; s.travel.Cancel(); assert(!s.bot.stopped); }
    // Lifecycle cancellation while a route is active, with/without takeover.
    { Scene s; s.start(); s.bot.alive=false;
      assert(s.travel.Update(1)==TravelStatus::Failed && s.bot.stopped==1); }
    { Scene s; s.start(); s.bot.teleport=true;
      assert(s.travel.Update(1)==TravelStatus::Failed && s.bot.stopped==1); }
    { Scene s; s.start(); ++s.bot.phase;
      assert(s.travel.Update(1)==TravelStatus::Failed && !s.bot.stopped); }
    { Scene s; s.start(); s.bot.combat=true;
      assert(s.travel.Update(1)==TravelStatus::TemporarilyBlocked && s.bot.stopped==1); }
    { Scene s; s.start(); s.foreign(); s.bot.combat=true; s.travel.Pause();
      assert(!s.bot.stopped && !s.bot.motion.expired && s.ai.last.delay==777); }
    // Long useful partial routes exceed eight dispatches, including two combat
    // resumptions. Completed physical segments, not planned endpoints, count.
    { Scene s; s.ai.partialEnd=5; s.start();
      for(int i=1;i<=19;++i) {
        s.finish(float(i*5));
        assert(s.travel.Update(1)==TravelStatus::TemporarilyBlocked);
        if(i==4 || i==9) {
          s.travel.Pause(); s.bot.combat=true;
          assert(s.travel.Update(UINT32_MAX)==TravelStatus::Paused);
          s.bot.combat=false; assert(s.travel.Resume()); s.travel.Update(0);
        }
        s.ai.partialEnd=float((i+1)*5);
        assert(s.travel.Update(1000)==TravelStatus::Running);
        if(i==5 || i==10) {
          s.travel.Pause(); assert(s.travel.Resume());
          assert(s.travel.Update(UINT32_MAX)==TravelStatus::Running);
        }
      }
      s.finish(100); assert(s.travel.Update(1)==TravelStatus::Arrived);
      assert(s.travel.GetAttempts()==22 && s.travel.GetFailedAttempts()==0);
      assert(s.travel.GetProgressSegments()==20); }
    // No-route and finished-without-progress share a cumulative failure budget;
    // a useful segment and pause/resume cannot erase preceding failures.
    { Scene s; s.ai.outcome=1; s.travel.Start(target,{10000,250,2});
      s.travel.Update(0); assert(s.travel.GetFailedAttempts()==1);
      s.ai.outcome=0; s.ai.partialEnd=40; s.travel.Update(250); s.finish(40);
      s.travel.Update(1); assert(s.travel.GetProgressSegments()==1);
      s.travel.Pause(); assert(s.travel.Resume()); s.travel.Update(0);
      s.travel.Update(250); s.finish(40); s.travel.Update(1);
      assert(s.travel.Update(250)==TravelStatus::Failed);
      assert(s.travel.GetFailure()==TravelFailure::AttemptLimit && s.ai.moveCalls==3);
      assert(s.travel.GetFailedAttempts()==2); }
    // A planned far endpoint is no evidence of actual progress. Even a finished
    // owned spline with sub-metre drift must consume the no-progress budget.
    for(float drift : {0.0f,0.1f,0.99f}) {
      Scene s; s.start({10000,250,2});
      for(int i=1;i<=2;++i) {
        s.bot.x=i*drift; s.bot.spline.finalized=true;
        s.travel.Update(1); s.travel.Update(250);
      }
      assert(s.travel.GetFailure()==TravelFailure::AttemptLimit && s.ai.moveCalls==2);
      assert(s.travel.GetProgressSegments()==0 && s.travel.GetFailedAttempts()==2);
    }
    // Detours can increase goal distance. Backtracking still cannot reset the
    // total dispatch budget, so oscillating endpoints terminate deterministically.
    { Scene s; s.ai.partialEnd=-10; s.start({10000,250,8,3});
      for(float x : {-10.0f,-20.0f,-10.0f}) {
        s.finish(x); s.travel.Update(1); s.ai.partialEnd=x==-10 ? -20 : -10;
        s.travel.Update(250);
      }
      assert(s.travel.GetFailure()==TravelFailure::DispatchLimit && s.ai.moveCalls==3);
      assert(s.travel.GetProgressSegments()==3 && s.travel.GetFailedAttempts()==0); }
    // Repeated combat interruption alone is not a route failure, but is bounded.
    { Scene s; s.start({10000,250,8,3});
      for(int i=0;i<3;++i) { s.travel.Pause(); assert(s.travel.Resume()); s.travel.Update(0); }
      assert(s.travel.GetFailure()==TravelFailure::DispatchLimit && s.ai.moveCalls==3);
      assert(s.travel.GetFailedAttempts()==0); }
    // Progress never resets the cumulative active-time deadline.
    { Scene s; s.ai.partialEnd=20; s.start({1000,250,8}); s.finish(20);
      s.travel.Update(400); s.travel.Update(250); s.finish(40);
      assert(s.travel.Update(350)==TravelStatus::Failed);
      assert(s.travel.GetFailure()==TravelFailure::Timeout); }
    // Start is the only reset boundary; arrival on the last allowed dispatch wins.
    { Scene s; s.start({10000,250,8,1}); s.finish(100);
      assert(s.travel.Update(1)==TravelStatus::Arrived);
      s.bot.x=0; s.ai.outcome=1; s.travel.Start(target,{10000,250,1}); s.travel.Update(0);
      s.travel.Update(250); assert(s.travel.GetFailedAttempts()==1);
      s.ai.outcome=0; s.travel.Start(target); s.travel.Update(0);
      assert(s.travel.GetAttempts()==1 && s.travel.GetFailedAttempts()==0 && s.travel.GetProgressSegments()==0);
      s.travel.Cancel(); }
    for(float invalid : {0.0f,6.0f,std::numeric_limits<float>::quiet_NaN()}) {
      Scene s; auto t=target; t.tolerance=invalid; s.travel.Start(t);
      assert(s.travel.GetStatus()==TravelStatus::Failed && !s.ai.moveCalls); }
    { Scene s; auto t=target; t.x=std::numeric_limits<float>::infinity(); s.travel.Start(t);
      assert(s.travel.GetFailure()==TravelFailure::InvalidTarget && !s.ai.moveCalls); }
    // Independent bot owners, even for identical goals.
    { Scene a,b; a.start(); b.start(); a.travel.Cancel();
      assert(!a.travel.ControlsMovement() && b.travel.ControlsMovement() && !b.bot.stopped); b.travel.Cancel(); }
}
'''
with tempfile.TemporaryDirectory(prefix="loa-botlife-travel-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run([sys.argv[2], "-x", "c++", "-std=c++20", "-O1", "-g", "-UNDEBUG",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(module),
                    "-", str(module / "BotLifeTravel.cpp"), "-o", str(binary)],
                   input=source, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife production travel and movement ownership passed", flush=True)
