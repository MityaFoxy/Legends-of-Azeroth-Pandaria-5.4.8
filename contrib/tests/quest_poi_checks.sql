-- Read-only diagnostics. Expected after 2026_10_02_01: PASS and
-- 12 unresolved headers. A count alone is not proof of repaired content.
SELECT '8306 return marker' AS test,
       IF(COUNT(*) = 1 AND SUM(BlobIndex = 1 AND Idx2 = 0 AND X = -6752
          AND Y = 824 AND VerifiedBuild = 0) = 1, 'PASS', 'FAIL') AS result
FROM quest_poi_points WHERE QuestID = 8306 AND Idx1 = 1;

SELECT 'three retired empty headers archived' AS test,
       IF(COUNT(*)=3, 'PASS', 'FAIL') AS result
FROM quest_poi_retired_archive
WHERE (QuestID,Idx1,ObjectiveIndex,QuestObjectiveId,MapID,WorldMapAreaId,Floor,Priority,Flags,VerifiedBuild)
 IN ((3379,1,-1,0,0,28,0,0,3,0), (10216,1,1,0,530,478,0,0,7,0),
     (29178,0,-1,0,568,781,0,0,7,0));

SELECT 'retired headers no longer active' AS test,
       IF(COUNT(*)=0, 'PASS', 'FAIL') AS result
FROM quest_poi WHERE (QuestID,Idx1) IN ((3379,1),(10216,1),(29178,0));

SELECT h.QuestID, h.Idx1, h.ObjectiveIndex, h.QuestObjectiveId,
       h.MapID, h.WorldMapAreaId, h.Floor, h.Flags
FROM quest_poi h
WHERE NOT EXISTS (SELECT 1 FROM quest_poi_points p
                  WHERE p.QuestID = h.QuestID AND p.Idx1 = h.Idx1)
ORDER BY h.QuestID, h.Idx1;
