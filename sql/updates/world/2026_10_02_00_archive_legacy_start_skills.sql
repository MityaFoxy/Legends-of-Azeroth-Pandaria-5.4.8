-- Original MoP 5.4.8: these 36 legacy SkillLine IDs are absent from
-- SkillLine.dbc, SkillRaceClassInfo.dbc and SkillLineAbility.dbc.
-- The loader already rejects them before populating PlayerInfo.
-- Preserve exact original payloads; never remove custom or conflicting rows.
-- Modern class skills come from Availability=1 SkillRaceClassInfo records.
CREATE TABLE IF NOT EXISTS playercreateinfo_skills_legacy_archive LIKE playercreateinfo_skills;
START TRANSACTION;
CREATE TEMPORARY TABLE _legacy_start_skills LIKE playercreateinfo_skills;
INSERT INTO _legacy_start_skills (raceMask,classMask,skill,`rank`,comment) VALUES
(0,1,26,0,'Warrior - Arms'),
(0,1,256,0,'Warrior - Fury'),
(0,1,257,0,'Warrior - Protection'),
(0,1,803,0,'Warrior - General'),
(0,2,184,0,'Paladin - Retribution'),
(0,2,267,0,'Paladin - Protection'),
(0,2,594,0,'Paladin - Holy'),
(0,4,50,0,'Hunter - Beast Mastery'),
(0,4,51,0,'Hunter - Survival'),
(0,4,163,0,'Hunter - Marksmanship'),
(0,8,38,0,'Rogue - Combat'),
(0,8,39,0,'Rogue - Subtlety'),
(0,8,253,0,'Rogue - Assassination'),
(0,8,797,0,'Rogue - General'),
(0,9,176,0,'Thrown'),
(0,16,56,0,'Priest - Holy'),
(0,16,78,0,'Priest - Shadow'),
(0,16,613,0,'Priest - Discipline'),
(0,32,770,0,'Death Knight - Blood'),
(0,32,771,0,'Death Knight - Frost'),
(0,32,772,0,'Death Knight - Unholy'),
(0,64,373,0,'Shaman - Enhancement'),
(0,64,374,0,'Shaman - Restoration'),
(0,64,375,0,'Shaman - Elemental'),
(0,64,801,0,'Shaman - General'),
(0,128,6,0,'Mage - Frost'),
(0,128,8,0,'Mage - Fire'),
(0,128,237,0,'Mage - Arcane'),
(0,128,799,0,'Mage - General'),
(0,256,354,0,'Warlock - Demonology'),
(0,256,355,0,'Warlock - Affliction'),
(0,256,593,0,'Warlock - Destruction'),
(0,256,802,0,'Warlock - General'),
(0,1024,134,0,'Druid - Feral'),
(0,1024,573,0,'Druid - Restoration'),
(0,1024,574,0,'Druid - Balance');

INSERT INTO playercreateinfo_skills_legacy_archive
SELECT s.* FROM playercreateinfo_skills s
JOIN _legacy_start_skills e USING (raceMask,classMask,skill)
WHERE s.`rank`=e.`rank` AND BINARY s.comment <=> BINARY e.comment
  AND NOT EXISTS (SELECT 1 FROM playercreateinfo_skills_legacy_archive a
    WHERE a.raceMask=s.raceMask AND a.classMask=s.classMask AND a.skill=s.skill);

DELETE s FROM playercreateinfo_skills s
JOIN _legacy_start_skills e USING (raceMask,classMask,skill)
JOIN playercreateinfo_skills_legacy_archive a USING (raceMask,classMask,skill)
WHERE s.`rank`=e.`rank` AND s.`rank`=a.`rank`
  AND BINARY s.comment <=> BINARY e.comment
  AND BINARY s.comment <=> BINARY a.comment;
DROP TEMPORARY TABLE _legacy_start_skills;
COMMIT;
