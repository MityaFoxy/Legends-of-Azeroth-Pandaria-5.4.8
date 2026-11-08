#!/usr/bin/env python3
"""Run native enchantment loading/selection/item generation with exported DB rows.

Real WDBC IDs/effects are checked separately. Database transport, DBC stores,
clock/logging and RNG are controlled test adapters; this is not a client test.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def body(text, signature):
    start = text.index(signature)
    end, depth = text.index('{', start) + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def dbc(path, expected_fields=None):
    data = path.read_bytes()
    magic, count, fields, size, strings = struct.unpack_from('<4s4I', data)
    assert magic == b'WDBC' and size == fields*4 and len(data) == 20+count*size+strings
    assert expected_fields is None or fields == expected_fields
    rows = list(struct.iter_unpack('<'+'I'*fields, data[20:20+count*size]))
    assert len({r[0] for r in rows}) == count
    return {r[0]:r for r in rows}, hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enchantments', required=True, type=Path)
    parser.add_argument('--items', required=True, type=Path, help='entry/name/ItemLevel/Quality/RandomProperty/RandomSuffix TSV')
    parser.add_argument('--dbc-dir', required=True, type=Path)
    parser.add_argument('--compiler', default='c++')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    props, phash = dbc(args.dbc_dir/'ItemRandomProperties.dbc', 8)
    suffixes, shash = dbc(args.dbc_dir/'ItemRandomSuffix.dbc', 13)
    effects, ehash = dbc(args.dbc_dir/'SpellItemEnchantment.dbc')
    rows = [line.split('\t') for line in args.enchantments.read_text().splitlines()]
    invalid, bad_effects, pools = [], [], defaultdict(list)
    for entry, ench, chance, kind in rows:
        entry, ench, kind = int(entry), int(ench), int(kind)
        assert kind in (0,1)
        pools[entry,kind].append((ench,float(chance)))
        store = props if kind == 0 else suffixes
        if ench not in store:
            invalid.append([entry,ench,kind])
            continue
        references = store[ench][2:5] if kind == 0 else store[ench][3:8]
        for effect in references:
            if effect and effect not in effects:
                bad_effects.append([entry,ench,kind,effect])
    report = dict(rows=len(rows), invalid_references=invalid, missing_effects=bad_effects,
                  invalid_by_type=dict(Counter(r[2] for r in invalid)),
                  dbc_sha256=dict(ItemRandomProperties=phash,ItemRandomSuffix=shash,SpellItemEnchantment=ehash),
                  affected_pool_weights={f'{e}:{t}':sum(c for _,c in v) for (e,t),v in pools.items()
                                         if e in (458,460,461,462,463,464,465)})

    manager = (ROOT/'src/server/game/Entities/Item/ItemEnchantmentMgr.cpp').read_text()
    item = (ROOT/'src/server/game/Entities/Item/Item.cpp').read_text()
    header = (ROOT/'src/server/game/Entities/Item/ItemEnchantmentMgr.h').read_text()
    source = r'''
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
using uint8=std::uint8_t; using uint32=std::uint32_t; using int32=std::int32_t;
unsigned errors=0;
#define TC_LOG_ERROR(...) do {++errors;} while(0)
#define TC_LOG_INFO(...) do {} while(0)
uint32 getMSTime() {return 1;} uint32 GetMSTimeDiffToNow(uint32) {return 0;}
double testRoll=30;
double rand_chance() {return testRoll;}
int irand(int lo,int hi) {assert(lo==0 && hi>0); return hi/2;}
struct Field {
    double value;
    uint32 GetUInt32() const {return uint32(value);}
    uint8 GetUInt8() const {return uint8(value);}
    float GetFloat() const {return float(value);}
};
struct Result {
    std::vector<std::array<Field,4>> rows; size_t index=0;
    Field* Fetch() {return rows.at(index).data();}
    bool NextRow() {return ++index<rows.size();}
};
using QueryResult=std::shared_ptr<Result>;
struct DB {
    std::string path;
    QueryResult Query(char const* sql) {
        assert(std::string(sql)=="SELECT entry, ench, chance, type FROM item_enchantment_template");
        auto result=std::make_shared<Result>(); std::ifstream file(path); assert(file);
        double entry,ench,chance,type;
        while(file>>entry>>ench>>chance>>type) result->rows.push_back({Field{entry},Field{ench},Field{chance},Field{type}});
        assert(!result->rows.empty()); return result;
    }
} WorldDatabase;
struct ItemRandomPropertiesEntry {uint32 ID;};
using ItemRandomSuffixEntry=ItemRandomPropertiesEntry;
struct Store {
    std::map<uint32,ItemRandomPropertiesEntry> rows;
    ItemRandomPropertiesEntry const* LookupEntry(uint32 id) const {
        auto i=rows.find(id); return i==rows.end()?nullptr:&i->second;
    }
} sItemRandomPropertiesStore,sItemRandomSuffixStore;
struct ItemTemplate {uint32 ItemId; int32 RandomProperty,RandomSuffix;};
struct Manager {
    std::map<uint32,ItemTemplate> rows;
    ItemTemplate const* GetItemTemplate(uint32 id) const {
        auto i=rows.find(id); return i==rows.end()?nullptr:&i->second;
    }
} objectManager;
Manager* sObjectMgr=&objectManager;
struct Item {static int32 GenerateItemRandomPropertyId(uint32);};
'''
    source += body(header,'enum class ItemRandomEnchantmentType')+';\n'
    source += manager[manager.index('struct EnchStoreItem'):manager.index('void LoadRandomEnchantmentsTable()')]
    source += body(manager,'void LoadRandomEnchantmentsTable(')+'\n'
    source += body(manager,'uint32 GetItemEnchantMod(')+'\n'
    source += body(item,'int32 Item::GenerateItemRandomPropertyId(')+'\n'
    source += 'int main(int argc,char** argv) { assert(argc==2); WorldDatabase.path=argv[1];\n'
    for name,store in [('sItemRandomPropertiesStore',props),('sItemRandomSuffixStore',suffixes)]:
        source += 'for(uint32 id:{'+','.join(f'{v}u' for v in store)+'}) '+name+'.rows[id]={id};\n'
    items = [line.split('\t') for line in args.items.read_text().splitlines()]
    for entry,name,level,quality,prop,suffix in items:
        source += f'objectManager.rows[{int(entry)}]={{{int(entry)},{int(prop)},{int(suffix)}}};\n'
    source += r'''
    LoadRandomEnchantmentsTable();
    // This roll reproduces the reported ID 281 on the inherited pool 460.
    testRoll=30;
    uint32 selected=GetItemEnchantMod(460,ItemRandomEnchantmentType::Property);
    int32 property=Item::GenerateItemRandomPropertyId(9791);
    std::cout<<"Ivycloth Tunic roll=30 selected="<<selected<<" generated="<<property<<" errors="<<errors<<"\n";
    if(!property || errors) return 1;
    unsigned generated=0;
    for(auto const& [id,item]:objectManager.rows) {
        for(unsigned step=0;step<10000;++step) {
            testRoll=(step+.5)/100.;
            int32 value=Item::GenerateItemRandomPropertyId(id);
            if(!value || (item.RandomProperty && value<0) || (item.RandomSuffix && value>0) || errors) {
                std::cerr<<"invalid generated property item="<<id<<" roll="<<testRoll<<" value="<<value<<"\n";
                return 1;
            }
            ++generated;
        }
    }
    std::cout<<"PASS: native loader/selection/generation, "<<generated<<" deterministic rolls for "
             <<objectManager.rows.size()<<" actual item templates; zero missing properties/suffixes\n";
}
'''
    with tempfile.TemporaryDirectory(prefix='loa-enchantment-regression-') as directory:
        cpp, binary = Path(directory)/'test.cpp',Path(directory)/'test'
        cpp.write_text(source)
        subprocess.run([args.compiler,'-std=c++20','-O1','-g','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-no-pie',str(cpp),'-o',str(binary)],check=True)
        env = dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
        result = subprocess.run([str(binary),str(args.enchantments.resolve())],env=env,text=True,capture_output=True)
    print(result.stdout,end='')
    print(result.stderr,end='',file=sys.stderr)
    report.update(native_exit_code=result.returncode,native_output=result.stdout,items=len(items),
                  status='passed' if result.returncode==0 and not invalid and not bad_effects else 'failed')
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"DBC references: {len(invalid)} invalid, {len(bad_effects)} missing enchantment effects")
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
