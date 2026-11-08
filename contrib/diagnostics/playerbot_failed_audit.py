#!/usr/bin/env python3
"""Count queued Action failures and, when present, their native branch evidence.

No reason is inferred from the action name. Uninstrumented and unmatched
events remain explicit coverage gaps. Successful alternatives do not turn
the preceding failure into a proven benign outcome.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import gzip
import json
import re

FIELDS = re.compile(r"\b(\w+)=('.*?'(?=\s+\w+=|$)|\([^)]*\)|[^\s]+)")
TRACE = re.compile(r' GUID=(\d+) map=(\d+) instance=(\d+) decision=(.*)$')

def lines(logs, name):
    # Logger rotations carry sortable date names; the unsuffixed current file
    # is last. Never lose .gz rotations or join across a missing map/instance.
    paths=sorted(logs.glob(name+'*'), key=lambda p:(p.name==name,p.name))
    for path in paths:
        opener=gzip.open if path.suffix=='.gz' else open
        with opener(path,'rt',errors='replace') as stream:
            for number,line in enumerate(stream,1):
                yield path.name,number,line.rstrip()

def audit(logs, source):
    outcomes=Counter();by_action=defaultdict(Counter);by_map=defaultdict(Counter)
    behavior=Counter();pending=defaultdict(list);next_ok=defaultdict(Counter)
    no_ok=Counter();unclosed=Counter();failed_bots=defaultdict(Counter)
    for file,number,line in lines(logs,'PlayerbotBehavior.log'):
        if ' TRACE [playerbots.behavior] ' not in line:continue
        match=TRACE.search(line)
        if not match:continue
        guid,mapid,instance,decision=match.groups();key=guid,mapid,instance
        if decision=='--- AI Tick ---':
            for action in pending.pop(key,[]):no_ok[action]+=1
            continue
        if not decision.startswith('A:'):continue
        action,sep,outcome=decision[2:].rpartition(' - ')
        if not sep:continue
        outcomes[outcome]+=1;by_action[action][outcome]+=1;by_map[mapid][outcome]+=1
        if outcome not in ('OK','FAILED'):continue
        behavior[(*key,action,outcome)]+=1
        if outcome=='FAILED':
            pending[key].append(action);failed_bots[action][guid]+=1
        else:
            for failed in pending.pop(key,[]):next_ok[failed][action]+=1
    for items in pending.values():
        for action in items:unclosed[action]+=1

    definitions=(source/'src/server/game/Miscellaneous/SharedDefines.h').read_text()
    symbols={int(value):name for name,value in re.findall(r'\b(SPELL_FAILED_\w+|SPELL_CAST_OK)\s*=\s*(\d+)',definitions)}
    diagnostic=Counter();reasons=Counter();profiles=defaultdict(Counter);details=defaultdict(Counter)
    examples=defaultdict(list);states=defaultdict(Counter);spells=Counter();parse_errors=[]
    for file,number,line in lines(logs,'PlayerbotExecution.log'):
        if 'event=action-execution ' not in line:continue
        row={k:v.strip("'") for k,v in FIELDS.findall(line)}
        try:
            key=row['bot'],row['map'],row['instance'],row['action'],'OK' if row['result']=='true' else 'FAILED'
            assert row['result'] in ('true','false') and row['raw'] in ('true','false')
            diagnostic[key]+=1
            if row['result']=='true':continue
            cause=row['reason'];code=int(row['cast_result'])
            native=symbols.get(code,str(code)) if code>=0 else 'not-prepared'
            profile=cause+(':'+native if cause=='cast/prepare-rejected' else '')
            reasons[profile]+=1;profiles[row['action']][profile]+=1
            details[row['action']][row['detail']]+=1
            spells[(row['action'],row['spell'],native)]+=1
            for field in ('alive','combat','moving','casting','mounted','root','stun','confuse','charmed','lost_control','target_alive','target_moving','form'):
                states[row['action']][field+'='+row.get(field,'missing')]+=1
            if len(examples[(row['action'],profile)])<3:
                examples[(row['action'],profile)].append(dict(file=file,line=number,time=line[:19],values=row))
        except (KeyError,ValueError,AssertionError) as error:
            parse_errors.append(dict(file=file,line=number,error=str(error)))
    mismatches=[]
    if diagnostic:
        for key in sorted(behavior.keys()|diagnostic.keys()):
            if behavior[key]!=diagnostic[key]:
                mismatches.append(dict(bot=key[0],map=key[1],instance=key[2],action=key[3],outcome=key[4],
                                       behavior=behavior[key],diagnostic=diagnostic[key]))
    actions={}
    for action,values in sorted(by_action.items(),key=lambda item:item[1]['FAILED'],reverse=True):
        if not values['FAILED']:continue
        actions[action]=dict(outcomes=dict(values),native_failure_reasons=dict(profiles[action].most_common()),
            details=dict(details[action].most_common()),states=dict(states[action]),
            next_ok_same_tick=dict(next_ok[action].most_common()),
            failed_without_later_ok_in_closed_tick=no_ok[action],unclosed_failure_tail=unclosed[action],
            failed_bots=dict(failed_bots[action].most_common()),
            examples={profile:rows for (name,profile),rows in examples.items() if name==action})
    return dict(action_decisions=sum(outcomes.values()),outcomes=dict(outcomes),by_map=dict(by_map),
        diagnostic_execution_count=sum(diagnostic.values()),native_failure_reasons=dict(reasons.most_common()),
        diagnostic_matches_behavior=bool(diagnostic) and not mismatches and not parse_errors,
        diagnostic_mismatches=mismatches,parse_errors=parse_errors,actions=actions,
        spell_results=[dict(action=a,spell=s,result=c,count=n) for (a,s,c),n in spells.most_common()],
        limitation='FAILED is an observed execution result, not a root-cause verdict. Same-tick OK proves another Action was accepted, not effect or harmlessness. Native reasons apply only to this run; never assign them retroactively to old counts.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs',type=Path);parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.logs,args.source)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('actions','spell_results','by_map','diagnostic_mismatches')},indent=2))

if __name__=='__main__':main()
