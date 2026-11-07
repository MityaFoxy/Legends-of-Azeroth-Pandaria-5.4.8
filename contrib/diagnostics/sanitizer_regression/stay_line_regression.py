#!/usr/bin/env python3
"""Compile the real line layout and Action; map collision/path are bounded doubles."""
from pathlib import Path
import subprocess
import sys
import tempfile
root, compiler = Path(sys.argv[1]), sys.argv[2]
base=root/'modules/mod_playerbots/src/strategy'

def block(text,signature):
    a=text.index(signature);b=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]

prefix=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>
#include <set>
using uint32=uint32_t;
constexpr int BOT_STATE_NON_COMBAT=1,BOT_STATE_COMBAT=0;
struct Event {};
struct Player;
struct Map {bool collision=true;bool CheckCollisionAndGetValidCoords(Player*,float,float,float,float&,float&,float&){return collision;}} map1,map2;
struct WorldLocation {
 uint32 map=uint32(-1);float x=0,y=0,z=0;
 WorldLocation()=default;WorldLocation(uint32 m,float a,float b,float c):map(m),x(a),y(b),z(c){}
 float GetPositionX()const{return x;}float GetPositionY()const{return y;}float GetPositionZ()const{return z;}uint32 GetMapId()const{return map;}
};
struct GroupReference {Player* p=nullptr;GroupReference* n=nullptr;Player* GetSource(){return p;}GroupReference* next(){return n;}};
struct Group {std::vector<GroupReference> refs;GroupReference* GetFirstMember(){return refs.empty()?nullptr:&refs[0];}
 void Set(std::vector<Player*> players){refs.resize(players.size());for(unsigned i=0;i<players.size();++i)refs[i]={players[i],i+1<players.size()?&refs[i+1]:nullptr};}
 unsigned GetMembersCount(){return refs.size()+100;}};
struct Player {
 Map* map=&map1;Group* group=nullptr;int phase=1;float x=100,y=100,z=10,angle=0;
 bool world=true,alive=true,bg=false,combat=false,vehicle=false,transport=false,casting=false,flight=false,root=false;
 bool IsInWorld(){return world;}bool IsAlive(){return alive;}bool InBattleground(){return bg;}bool IsInCombat(){return combat;}
 bool GetVehicle(){return vehicle;}bool GetTransport(){return transport;}bool IsNonMeleeSpellCasted(bool,bool,bool){return casting;}
 bool IsInFlight(){return flight;}Map* GetMap(){return map;}uint32 GetMapId(){return 1;}Group* GetGroup(){return group;}
 bool InSamePhase(Player* p){return phase==p->phase;}
 float GetPositionX(){return x;}float GetPositionY(){return y;}float GetPositionZ(){return z;}float GetOrientation(){return angle;}
 float GetDistance(float a,float b,float c){return std::sqrt((x-a)*(x-a)+(y-b)*(y-b)+(z-c)*(z-c));}
};
struct PlayerbotAI {Player* bot;Player* master;int state=1;bool canMove=true,moveFromGroup=false;std::string configuredFormation="shield";
 Player* GetMaster(){return master;}int GetState(){return state;}bool CanMove(){return canMove;}
 bool HasStrategy(std::string,int){return moveFromGroup;}};
struct AiNamedObject {PlayerbotAI* botAI;Player* bot;AiNamedObject(PlayerbotAI* ai,std::string):botAI(ai),bot(ai->bot){}Player* GetMaster(){return botAI->master;}};
struct Action:AiNamedObject {using AiNamedObject::AiNamedObject;virtual ~Action()=default;
 virtual bool Execute(Event){return false;}virtual bool isUseful(){return true;}virtual bool isPossible(){return true;}};
struct MovementAction:Action {using Action::Action;bool path=true;int calls=0;WorldLocation destination;
 bool IsMovingAllowed(){return !bot->root&&!bot->flight;}
 bool MoveTo(uint32 m,float x,float y,float z,bool,bool,bool normal,bool exact){++calls;assert(normal&&exact);destination=WorldLocation(m,x,y,z);return path;}};
struct Config{float followDistance=5;} config;Config* sPlayerbotAIConfig=&config;
'''
h=(base/'value/Formations.h').read_text();s=(base/'value/Formations.cpp').read_text()
code=prefix
for name in ['Formation','MoveFormation','MoveAheadFormation']:
    code+=block(h,'class '+name+' :')+';\n'
code+='WorldLocation Formation::NullLocation = WorldLocation();\n'
for signature in ['bool IsSameLocation','bool Formation::IsNullLocation','WorldLocation MoveAheadFormation::GetLocation()', 'WorldLocation MoveFormation::MoveLine','WorldLocation MoveFormation::MoveSingleLine']:
    code+=block(s,signature)+'\n'
code+=block(s,'class LineFormation :')+';\n'+block(s,'WorldLocation GetLineFormationLocation')+'\n'
code+=block((base/'actions/StayActions.h').read_text(),'class StayLineAction :')+';\n'
actions=(base/'actions/StayActions.cpp').read_text()
for name in ['CanFormLine','isUseful','isPossible','Execute']:
    code+=block(actions,'bool StayLineAction::'+name)+'\n'
code+=r'''
int main(){
 Player bot,master,other;Group group;bot.group=master.group=other.group=&group;
 group.Set({&master,&bot,nullptr});PlayerbotAI ai{&bot,&master};StayLineAction a(&ai);
 auto loc=GetLineFormationLocation(&ai);assert(loc.GetMapId()==1);assert(std::abs(loc.x-100)<0.001&&std::abs(loc.y-98)<0.001);
 assert(a.isUseful()&&a.isPossible());assert(a.Execute({}));assert(a.calls==1&&ai.configuredFormation=="shield");
 bot.x=loc.x;bot.y=loc.y;assert(!a.isUseful());assert(!a.Execute({}));assert(a.calls==1);bot.y=100;
 a.path=false;assert(!a.Execute({}));a.path=true;
 map1.collision=false;int n=a.calls;assert(!a.Execute({}));assert(a.calls==n);map1.collision=true;
 for(bool* flag:{&bot.bg,&master.bg,&bot.combat,&master.combat,&bot.casting,&bot.vehicle,&master.vehicle,&bot.transport,&master.transport,&bot.root,&bot.flight,&master.flight,&ai.moveFromGroup}){
  *flag=true;assert(!a.isUseful());assert(!a.Execute({}));*flag=false;}
 ai.canMove=false;assert(!a.Execute({}));ai.canMove=true;
 ai.state=0;assert(!a.Execute({}));ai.state=1;
 master.alive=false;assert(!a.Execute({}));master.alive=true;
 master.world=false;assert(!a.Execute({}));master.world=true;
 master.map=&map2;assert(!a.Execute({}));master.map=&map1;
 master.phase=2;assert(!a.Execute({}));master.phase=1;
 master.group=nullptr;assert(!a.Execute({}));master.group=&group;
 ai.master=&bot;assert(!a.Execute({}));ai.master=nullptr;assert(!a.Execute({}));ai.master=&master;
 bot.group=nullptr;assert(!a.Execute({}));bot.group=&group;
 // Actual roster, rather than persistent group count, controls safe insertion.
 group.Set({nullptr,&master,nullptr,&bot,&other});other.world=false;
 loc=GetLineFormationLocation(&ai);assert(std::abs(loc.y-98)<0.001);other.world=true;
 // All members occupy distinct positions across the five-member row boundary.
 Player members[6];std::vector<Player*> roster{&master};for(auto& p:members){p.group=&group;roster.push_back(&p);}
 for(unsigned count:{1u,2u,5u,6u}){
  group.Set(std::vector<Player*>(roster.begin(),roster.begin()+count));std::set<std::pair<int,int>> positions;
  for(unsigned i=1;i<count;++i){ai.bot=roster[i];auto l=GetLineFormationLocation(&ai);assert(!Formation::IsNullLocation(l));positions.insert({int(std::round(l.x)),int(std::round(l.y))});}
  assert(positions.size()==count-1);
 }
 ai.bot=&bot;group.Set({&master});assert(Formation::IsNullLocation(GetLineFormationLocation(&ai)));
}
'''
with tempfile.TemporaryDirectory(prefix='loa-stay-line-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([compiler,'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Line geometry, movement guards and failure propagation passed')
