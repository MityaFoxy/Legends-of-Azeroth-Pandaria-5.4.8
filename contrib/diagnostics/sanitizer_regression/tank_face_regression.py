#!/usr/bin/env python3
"""Execute real tank-face selection with controlled collision projections.

Checks action dispatch and candidate selection, not real mesh/liquid geometry.
Use --verify-mutations to verify that the safety assertions detect regressions.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
text = (root / "modules/mod_playerbots/src/strategy/actions/MovementActions.cpp").read_text()


def method(signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


source = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <deque>
#include <list>
#include <type_traits>
#include <vector>
constexpr float CONTACT_DISTANCE=0.5f;
struct Position {
    float x=0,y=0,z=0;
    Position()=default;
    Position(float a,float b,float c):x(a),y(b),z(c) {}
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }
    float GetExactDist(Position const& p) const { return std::hypot(std::hypot(x-p.x,y-p.y),z-p.z); }
    float GetExactDist2d(float a,float b) const { return std::hypot(x-a,y-b); }
    static float NormalizeOrientation(float a) { a=std::fmod(a,2*M_PI); return a<0?a+2*M_PI:a; }
};
bool same(Position const& a,Position const& b) { return a.GetExactDist(b)<0.0001f; }
struct Projection { Position point; bool clear=true; };
struct Map {
    std::deque<Projection> replies;
    int calls=0;
    bool CheckCollisionAndGetValidCoords(void*,float,float,float,float& x,float& y,float& z) {
        ++calls; assert(!replies.empty());
        auto next=replies.front(); replies.pop_front();
        x=next.point.x; y=next.point.y; z=next.point.z; return next.clear;
    }
};
struct Unit : Position {
    using Position::GetExactDist;
    bool group=true,melee=true,moving=false;
    float angle=1;
    int nearCalls=0;
    Map map;
    void* GetGroup() { return group?this:nullptr; }
    bool IsWithinMeleeRange(Unit*) const { return melee; }
    bool isMoving() const { return moving; }
    float GetAngle(Position const*) const { return angle; }
    float GetExactDist(Unit const* u) const { return Position::GetExactDist(*u); }
    float GetMeleeRange(Unit*) const { return 5; }
    float GetCombatReach() const { return 1.5f; }
    int GetMapId() const { return 529; }
    Map* GetMap() { return &map; }
    void GetNearPoint(Unit* bot,float& a,float& b,float& c,float,float) {
        ++nearCalls;
        // The requested candidate is useful before collision correction.
        a=bot->x+10; b=bot->y+10; c=bot->z;
    }
};
struct FleeInfo {};
struct Event {};
enum class MovementPriority { MOVEMENT_COMBAT };
struct CombatFormationMoveAction {
    Unit* bot;
    Position GetNearestPosition(std::vector<Position> const&);
};
struct TankFaceAction : CombatFormationMoveAction {
    Unit* target;
    bool aggro=true,moveResult=true;
    float averageAngle=1;
    std::list<FleeInfo> history;
    std::deque<bool> fleeReplies;
    int moves=0,fleeChecks=0;
    Position destination;
    TankFaceAction(Unit* b,Unit* t):CombatFormationMoveAction{b},target(t) {}
    template<class T> T value() {
        if constexpr (std::is_same_v<T,Unit*>) return target;
        else return history;
    }
    float AverageGroupAngle(Unit*,bool) { return averageAngle; }
    bool CheckLastFlee(float,std::list<FleeInfo>&) {
        ++fleeChecks;
        if(fleeReplies.empty()) return true;
        bool result=fleeReplies.front(); fleeReplies.pop_front(); return result;
    }
    bool MoveTo(int map,float x,float y,float z,bool idle,bool react,bool normalOnly,bool exact,MovementPriority priority) {
        assert(map==529 && !idle && !react && !normalOnly && exact && priority==MovementPriority::MOVEMENT_COMBAT);
        ++moves; destination={x,y,z}; return moveResult;
    }
    bool Execute(Event);
};
#define AI_VALUE(type,name) value<type>()
#define AI_VALUE2(type,name,qualifier) aggro
''' + method("Position CombatFormationMoveAction::GetNearestPosition(") + "\n" + method("bool TankFaceAction::Execute(") + r'''
int main() {
    Position start{1129.7812f,1232.9813f,-60.3687f};
    Position collapsed{1129.7811f,1232.988f,-59.555866f};
    Position useful{start.x+3,start.y+2,start.z};
    // Either side can collapse after projection. Select the other side.
    for(bool first:{true,false}) {
        Unit bot,target; static_cast<Position&>(bot)=start;
        TankFaceAction action(&bot,&target);
        bot.map.replies=first?std::deque<Projection>{{collapsed},{useful}}:std::deque<Projection>{{useful},{collapsed}};
        assert(action.Execute({}));
        assert(action.moves==1 && same(action.destination,useful));
        assert(bot.map.calls==2 && target.nearCalls==2 && action.fleeChecks==1);
    }
    // Both collapsed/vertical candidates must cause no MoveTo or flee check.
    for(float height:{0.f,0.812834f,20.f,-20.f}) {
        Unit bot,target; static_cast<Position&>(bot)=start;
        TankFaceAction action(&bot,&target);
        bot.map.replies={{{start.x,start.y,start.z+height}},{collapsed}};
        assert(!action.Execute({}) && !action.moves && !action.fleeChecks);
    }
    // The contact-distance boundary uses XY even with a large Z difference.
    for(float offset:{0.49f,0.5f,0.51f}) {
        Unit bot,target; TankFaceAction action(&bot,&target);
        Position candidate{offset,0,10};
        bot.map.replies={{candidate},{candidate}};
        assert(action.Execute({})==(offset>CONTACT_DISTANCE));
        assert(action.moves==(offset>CONTACT_DISTANCE?1:0));
    }
    // Useful candidates near world origin still select a supplied point.
    {
        Unit bot,target; TankFaceAction action(&bot,&target);
        Position far{4,0,0},near{2,0,0};
        bot.map.replies={{far},{near}};
        assert(action.Execute({}) && same(action.destination,near));
        assert(same(action.GetNearestPosition({near,far}),near));
        assert(same(action.GetNearestPosition({}),{}));
    }
    // Collision and recent-flee vetoes still apply to both sides.
    for(bool collision:{true,false}) {
        Unit bot,target; TankFaceAction action(&bot,&target);
        bot.map.replies={{{2,0,0},collision},{{3,0,0},collision}};
        action.fleeReplies={false,false};
        assert(!action.Execute({}) && !action.moves);
        assert(action.fleeChecks==(collision?2:0));
    }
    {
        Unit bot,target; TankFaceAction action(&bot,&target);
        bot.map.replies={{{2,0,0},false},{{3,0,0},true}};
        assert(action.Execute({}) && same(action.destination,{3,0,0}));
    }
    // Existing combat eligibility guards must not issue candidate queries.
    for(int guard=0;guard<7;++guard) {
        Unit bot,target; TankFaceAction action(&bot,&target);
        if(guard==0) action.target=nullptr;
        if(guard==1) bot.group=false;
        if(guard==2) bot.melee=false;
        if(guard==3) target.moving=true;
        if(guard==4) action.aggro=false;
        if(guard==5) action.averageAngle=0;
        if(guard==6) target.angle=action.averageAngle+M_PI;
        assert(!action.Execute({}) && !action.moves && !bot.map.calls && !target.nearCalls);
    }
    // A downstream navigation refusal must remain a failed action.
    {
        Unit bot,target; TankFaceAction action(&bot,&target);
        bot.map.replies={{{2,0,0}},{{3,0,0}}}; action.moveResult=false;
        assert(!action.Execute({}) && action.moves==1);
    }
}
'''

with tempfile.TemporaryDirectory(prefix="loa-tank-face-") as directory:
    binary = Path(directory) / "regression"
    environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                       UBSAN_OPTIONS="halt_on_error=1")

    def run(code, mutation=None):
        subprocess.run([sys.argv[2], "-x", "c++", "-std=c++20", "-O1", "-g",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-", "-o", str(binary)],
                       input=code, text=True, check=True)
        result = subprocess.run([str(binary)], env=environment, capture_output=True, text=True)
        if mutation:
            assert result.returncode != 0 and "Assertion" in result.stderr, (mutation, result.stderr)
            print(f"Mutation {mutation}: rejected by assertion", flush=True)
        else:
            assert result.returncode == 0, result.stderr

    run(source)
    if "--verify-mutations" in sys.argv[3:]:
        for label, original, replacement in (
            ("height-counts-as-reposition", "bot->GetExactDist2d(x, y)", "bot->GetExactDist(Position(x,y,z))"),
            ("no-progress-accepted", "bot->GetExactDist2d(x, y) <= CONTACT_DISTANCE", "false"),
            ("world-origin-selected", "Position result = positions.front();", "Position result;"),
        ):
            assert source.count(original) == 1, label
            run(source.replace(original, replacement, 1), label)
print("Tank-face projected candidate selection regression passed", flush=True)
