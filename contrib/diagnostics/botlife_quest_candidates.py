#!/usr/bin/env python3
"""Read-only shortlist of equipped random bots near supported kill-quest givers.

This is a preflight aid, not a replacement for native CanTakeQuest/readiness.
Never prints connection credentials or changes characters, quests or positions.
"""
import argparse
import math
import os
import re
import subprocess
from pathlib import Path

from sanitizer_soak import setting
from botlife_quest_dependencies import QuestDependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = args.config.read_text()
    host, port, user, password, characters = setting(config, "CharacterDatabaseInfo").split(";")
    world = setting(config, "WorldDatabaseInfo").split(";")[-1]
    auth = setting(config, "LoginDatabaseInfo").split(";")[-1]
    if not all(re.fullmatch(r"[A-Za-z0-9_]+", name) for name in (characters, world, auth)):
        raise RuntimeError("Unsafe database identifier")
    unsupported_flags = sum((0x2, 0x4, 0x400, 0x1000, 0x2000, 0x8000, 0x10000, 0x80000, 0x100000, 0x200000))
    def sql(query):
        result = subprocess.run(["mysql", "--connect-timeout=5", "-h", host, "-P", port, "-u", user,
                                 "-N", "-B", characters, "-e", "SET SESSION max_execution_time=30000; " + query],
                                env=dict(os.environ, MYSQL_PWD=password), capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise RuntimeError("Read-only candidate query failed: " + result.stderr.replace(password, "[redacted]"))
        return [line.split("\t") for line in result.stdout.splitlines()]

    # Do not cross-join every character with every world spawn in SQL.
    quests = sql(f"""
SELECT q.ID,q.QuestLevel,q.MinLevel,COALESCE(q.AllowableRaces,0),COALESCE(qa.AllowableClasses,0),
       COALESCE(qa.MaxLevel,0),g.map,g.position_x,g.position_y,q.LogTitle
FROM `{world}`.quest_template q
JOIN `{world}`.creature_queststarter qs ON qs.quest=q.ID
JOIN `{world}`.creature g ON g.id=qs.id AND g.phaseMask=1 AND g.phaseId=0 AND g.phaseGroup=0
LEFT JOIN `{world}`.quest_template_addon qa ON qa.ID=q.ID
WHERE q.QuestType=2 AND q.QuestInfoID=0 AND q.SuggestedGroupNum<=1
  AND q.TimeAllowed=0 AND q.StartItem=0 AND q.FlagsEx=0 AND (q.Flags & {unsupported_flags})=0
  AND q.RewardChoiceItemID1=0 AND q.QuestPackageID=0
  AND COALESCE(qa.SpecialFlags,0)=0 AND COALESCE(qa.SourceSpellID,0)=0
  AND COALESCE(qa.ScriptName,'')=''
  AND COALESCE(qa.RequiredSkillID,0)=0 AND COALESCE(qa.RequiredMinRepFaction,0)=0
  AND EXISTS (SELECT 1 FROM `{world}`.quest_objective o WHERE o.questId=q.ID)
  AND NOT EXISTS (SELECT 1 FROM `{world}`.quest_objective o WHERE o.questId=q.ID
                  AND (o.type<>0 OR o.flags<>0 OR o.amount<=0 OR o.objectId<=0))
  AND EXISTS (SELECT 1 FROM `{world}`.creature_questender e WHERE e.quest=q.ID)
  AND NOT EXISTS (SELECT 1 FROM `{world}`.game_event_creature e WHERE e.guid=g.guid)
  AND NOT EXISTS (SELECT 1 FROM `{world}`.pool_creature p WHERE p.guid=g.guid)
""")
    bots = sql(f"""
SELECT c.guid,c.name,c.race,c.class,c.level,c.map,c.position_x,c.position_y,c.health,c.talentTree
FROM characters c JOIN `{auth}`.account a ON a.id=c.account AND a.username REGEXP '^RNDBOT[0-9]+$'
WHERE c.online=0 AND (c.playerFlags & 16)=0 AND c.health>1
  AND EXISTS (SELECT 1 FROM character_inventory i WHERE i.guid=c.guid AND i.bag=0 AND i.slot IN (15,17))
  AND (c.level<10 OR (
    EXISTS (SELECT 1 FROM character_inventory i WHERE i.guid=c.guid AND i.bag=0 AND i.slot=4) AND
    EXISTS (SELECT 1 FROM character_inventory i WHERE i.guid=c.guid AND i.bag=0 AND i.slot=6)))
""")
    dependencies = QuestDependencies(sql(f"""
SELECT q.ID,COALESCE(a.PrevQuestID,0),COALESCE(a.NextQuestID,0),COALESCE(a.ExclusiveGroup,0)
FROM `{world}`.quest_template q LEFT JOIN `{world}`.quest_template_addon a ON a.ID=q.ID
"""))
    rewarded = {}
    for guid, quest in sql("SELECT guid,quest FROM character_queststatus_rewarded"):
        rewarded.setdefault(guid, set()).add(int(quest))
    active = {}
    for guid, quest, status in sql("SELECT guid,quest,status FROM character_queststatus"):
        active.setdefault(guid, {})[int(quest)] = int(status)
    candidates = {}
    for bot in bots:
        guid, name, race, cls, level, map_id, x, y, hp, spec = bot
        race, cls, level = int(race), int(cls), int(level)
        for quest in quests:
            qid, qlevel, minimum, races, classes, maximum, qmap, qx, qy, title = quest
            if map_id != qmap or not level-5 <= int(qlevel) <= level+2 or int(minimum)>level:
                continue
            if int(maximum) and int(maximum)<level or int(races) and not int(races)&(1<<(race-1)) or int(classes) and not int(classes)&(1<<(cls-1)):
                continue
            distance = math.hypot(float(x)-float(qx), float(y)-float(qy))
            key = (guid, qid)
            if distance <= 1500 and dependencies.rejection(int(qid), rewarded.get(guid, set()), active.get(guid, {})):
                continue
            if distance <= 1500 and (key not in candidates or distance < candidates[key][0]):
                candidates[key] = (distance, guid, name, str(cls), str(level), map_id, qid, qlevel, title, hp, spec)
    print("distance\tguid\tname\tclass\tlevel\tmap\tquest\tquestLevel\ttitle\thp\tspec")
    for row in sorted(candidates.values())[:100]:
        print("\t".join((str(round(row[0])), *row[1:])))


if __name__ == "__main__":
    main()
