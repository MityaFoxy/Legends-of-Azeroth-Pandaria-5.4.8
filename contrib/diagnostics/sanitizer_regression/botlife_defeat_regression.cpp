#include "BotLifeDefeats.h"
#include <cassert>
#include <limits>

int main()
{
    using namespace BotLife;
    OpponentKey a{1, 2, 30, 100, true}, b{1, 2, 30, 101, true};
    DefeatHistory memory;
    assert(memory.Record(a, 0) == 1 && !memory.Avoid(a, 0));
    assert(memory.Record(b, 1) == 1 && !memory.Avoid(a, 1));
    assert(memory.Record(a, 2) == 2 && memory.Avoid(a, 2));
    assert(!memory.Avoid(b, 2)); // Same template, different creature.
    auto other = a; other.instance++;
    assert(!memory.Avoid(other, 2));
    other = a; other.map++;
    assert(!memory.Avoid(other, 2));
    other = a; other.persistent = false;
    assert(!memory.Avoid(other, 2)); // Runtime identity is a different namespace.
    assert(memory.Avoid(a, DefeatHistory::LifetimeMs + 1));
    assert(!memory.Avoid(a, DefeatHistory::LifetimeMs + 2));
    assert(memory.Record(a, DefeatHistory::LifetimeMs + 3) == 1);
    DefeatHistory wrap;
    auto const end = std::numeric_limits<uint32_t>::max();
    wrap.Record(a, end - 10);
    wrap.Record(a, end - 5);
    assert(wrap.Avoid(a, 5));
    assert(!wrap.Avoid(a, DefeatHistory::LifetimeMs));
    DefeatHistory bounded;
    bounded.Record(a, 0); bounded.Record(a, 1);
    for (unsigned i = 0; i < DefeatHistory::Capacity; ++i)
        bounded.Record({1, 2, 30, 1000 + i, true}, 2 + i);
    assert(!bounded.Avoid(a, 100));
    assert(bounded.Record({}, 100) == 0);
    AreaDefeatHistory areas;
    DefeatArea first{1,2,1,{0,0,0},{100,0,0}};
    assert(areas.Record(first,0)==1 && areas.Active(1,2,1,0).empty());
    auto near=first; near.origin.x=8;
    assert(areas.Record(near,1)==2);
    assert(areas.Active(1,2,1,1).size()==1);
    assert(areas.Active(1,2,1,1)[0].origin.x==0); // No drifting/chain merging.
    near.origin.x=16; assert(areas.Record(near,2)==1);
    near.origin={0,0,5}; assert(areas.Record(near,3)==1); // Different floor.
    near=first; ++near.instance; assert(areas.Record(near,4)==1);
    near=first; ++near.map; assert(areas.Record(near,5)==1);
    near=first; ++near.phase; assert(areas.Record(near,6)==1);
    assert(areas.Active(1,2,1,DefeatHistory::LifetimeMs).size()==1);
    assert(areas.Active(1,2,1,DefeatHistory::LifetimeMs+1).empty());
    AreaDefeatHistory areaWrap;
    areaWrap.Record(first,end-10); areaWrap.Record(first,end-5);
    assert(areaWrap.Active(1,2,1,5).size()==1);
    assert(areaWrap.Active(1,2,1,DefeatHistory::LifetimeMs).empty());
    AreaDefeatHistory areaBound;
    areaBound.Record(first,0); areaBound.Record(first,1);
    for(unsigned i=1;i<=DefeatHistory::Capacity;++i) {
        near=first; near.origin.x=i*20; areaBound.Record(near,i+1);
    }
    assert(areaBound.Active(1,2,1,100).empty());
    near.origin.x=std::numeric_limits<float>::quiet_NaN();
    assert(areaBound.Record(near,100)==0);
}
