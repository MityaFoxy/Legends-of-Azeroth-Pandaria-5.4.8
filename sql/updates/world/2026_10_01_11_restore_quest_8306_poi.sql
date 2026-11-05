-- Restore one missing return marker, not quest objectives or quest availability.
-- Sources and rejected alternatives: doc/startup_objectives_respawn_poi_audit.md.
-- MaNGOS Four 8b798ac6: quest_poi 8306/1 matches the current header exactly;
-- quest_poi_points (8306,1,-6752,824). MoPDB/SFDB corroborate this position.
-- VerifiedBuild=0: reconstructed mapping, not a new packet capture.
-- Insert only for exact expected headers and wholly absent point groups.
-- Existing/custom headers and points are never overwritten or removed.

START TRANSACTION;

INSERT INTO `quest_poi_points`
    (`QuestID`, `BlobIndex`, `Idx1`, `Idx2`, `X`, `Y`, `VerifiedBuild`)
SELECT 8306, 1, 1, 0, -6752, 824, 0
FROM `quest_poi` h
WHERE h.`QuestID` = 8306 AND h.`Idx1` = 1
  AND h.`ObjectiveIndex` = -1 AND h.`QuestObjectiveId` = 0
  AND h.`MapID` = 1 AND h.`WorldMapAreaId` = 261
  AND h.`Floor` = 0 AND h.`Priority` = 0 AND h.`Flags` = 1
  AND h.`VerifiedBuild` = 0
  AND NOT EXISTS (SELECT 1 FROM `quest_poi_points` p
                  WHERE p.`QuestID` = h.`QuestID` AND p.`Idx1` = h.`Idx1`);

COMMIT;
