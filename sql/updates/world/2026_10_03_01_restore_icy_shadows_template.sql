-- The previous binding cleanup archived entry 742 along with its geometry.
-- The template is used when the AreaTrigger is created even without a C++
-- script. Restore its original payload and leave the unregistered script unset.
INSERT INTO `spell_areatrigger_template`
 (`Entry`,`Flags`,`CollisionType`,`Radius`,`ScaleX`,`ScaleY`,`ScriptName`)
SELECT a.`Entry`,a.`Flags`,a.`CollisionType`,a.`Radius`,a.`ScaleX`,a.`ScaleY`,''
FROM `spell_areatrigger_template_disabled_archive` a
WHERE a.`Entry` = 742 AND a.`Flags` = 0 AND a.`CollisionType` = 0
  AND a.`Radius` = 7 AND a.`ScaleX` = 0 AND a.`ScaleY` = 0
  AND a.`ScriptName` = 'sat_icy_shadows'
  AND NOT EXISTS (SELECT 1 FROM `spell_areatrigger_template` t WHERE t.`Entry` = 742);
