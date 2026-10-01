-- 2026_10_01_01 introduced this relation, but Rin'ji (7780) has no spawn or
-- questgiver flag in this MoP world DB. Quest 2742 was removed before MoP.
-- Undo only our added relation; keep the NPC template and escort waypoints.
DELETE FROM `creature_queststarter`
WHERE `id` = 7780 AND `quest` = 2742;
