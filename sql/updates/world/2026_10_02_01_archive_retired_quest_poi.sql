-- Three exact empty POI headers belonging to quests already deprecated in
-- Cataclysm build 15595 (TrinityCore 4.3.4/005_quest_template.sql).
-- Not a blanket empty-POI cleanup. Active quests, points, other headers and
-- quest templates are untouched. See doc/startup_objectives_respawn_poi_audit.md.
CREATE TABLE IF NOT EXISTS quest_poi_retired_archive LIKE quest_poi;
START TRANSACTION;
CREATE TEMPORARY TABLE _retired_poi_expected LIKE quest_poi;
INSERT INTO _retired_poi_expected
 (QuestID,Idx1,ObjectiveIndex,QuestObjectiveId,MapID,WorldMapAreaId,Floor,Priority,Flags,VerifiedBuild) VALUES
 (3379,1,-1,0,0,28,0,0,3,0),
 (10216,1,1,0,530,478,0,0,7,0),
 (29178,0,-1,0,568,781,0,0,7,0);

INSERT INTO quest_poi_retired_archive
SELECT h.* FROM quest_poi h
JOIN _retired_poi_expected e USING
 (QuestID,Idx1,ObjectiveIndex,QuestObjectiveId,MapID,WorldMapAreaId,Floor,Priority,Flags,VerifiedBuild)
JOIN quest_template q ON q.ID=h.QuestID
WHERE q.VerifiedBuild=15595
 AND ((q.ID=3379 AND q.Flags=16392)
   OR (q.ID=10216 AND q.Flags=278664)
   OR (q.ID=29178 AND q.Flags=16520))
 AND NOT EXISTS (SELECT 1 FROM quest_poi_points p WHERE p.QuestID=h.QuestID AND p.Idx1=h.Idx1)
 AND NOT EXISTS (SELECT 1 FROM quest_poi_retired_archive a WHERE a.QuestID=h.QuestID AND a.Idx1=h.Idx1);

-- Require both the expected payload and a matching archival copy. A custom
-- header, reactivated quest, newly supplied points or archive conflict blocks removal.
DELETE h FROM quest_poi h
JOIN _retired_poi_expected e USING
 (QuestID,Idx1,ObjectiveIndex,QuestObjectiveId,MapID,WorldMapAreaId,Floor,Priority,Flags,VerifiedBuild)
JOIN quest_poi_retired_archive a USING
 (QuestID,Idx1,ObjectiveIndex,QuestObjectiveId,MapID,WorldMapAreaId,Floor,Priority,Flags,VerifiedBuild)
JOIN quest_template q ON q.ID=h.QuestID
WHERE q.VerifiedBuild=15595
 AND ((q.ID=3379 AND q.Flags=16392)
   OR (q.ID=10216 AND q.Flags=278664)
   OR (q.ID=29178 AND q.Flags=16520))
 AND NOT EXISTS (SELECT 1 FROM quest_poi_points p WHERE p.QuestID=h.QuestID AND p.Idx1=h.Idx1);
DROP TEMPORARY TABLE _retired_poi_expected;
COMMIT;
