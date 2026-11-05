/*
* This file is part of the Legends of Azeroth Pandaria Project. See THANKS file for Copyright information
*
* This program is free software; you can redistribute it and/or modify it
* under the terms of the GNU General Public License as published by the
* Free Software Foundation; either version 2 of the License, or (at your
* option) any later version.
*
* This program is distributed in the hope that it will be useful, but WITHOUT
* ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
* FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
* more details.
*
* You should have received a copy of the GNU General Public License along
* with this program. If not, see <http://www.gnu.org/licenses/>.
*/

/* ScriptData
SDName: Hinterlands
SD%Complete: 100
SDComment: Quest support: 836
SDCategory: The Hinterlands
EndScriptData */

/* ContentData
npc_00x09hl
EndContentData */

#include "ScriptMgr.h"
#include "ScriptedCreature.h"
#include "ScriptedEscortAI.h"
#include "Player.h"

/*######
## npc_00x09hl
######*/

enum eOOX
{
    SAY_OOX_START           = 0,
    SAY_OOX_AGGRO           = 1,
    SAY_OOX_AMBUSH          = 3,
    SAY_OOX_AMBUSH_REPLY    = 4,
    SAY_OOX_END             = 5,

    QUEST_RESQUE_OOX_09     = 836,

    NPC_MARAUDING_OWL       = 7808,
    NPC_VILE_AMBUSHER       = 7809,

    FACTION_ESCORTEE_A      = 774,
    FACTION_ESCORTEE_H      = 775
};

enum Rinji
{
    QUEST_RINJI_IS_TRAPPED = 2742,
    NPC_RANGER = 2694,
    NPC_OUTRUNNER = 2691,
    GO_RINJIS_CAGE = 142036
};

Position const RinjiAmbushSpawn[2] =
{
    {191.296204f, -2839.329346f, 107.388f, 0.0f},
    {70.972466f, -2848.674805f, 109.459f, 0.0f}
};

Position const RinjiAmbushMoveTo[2] =
{
    {166.630386f, -2824.780273f, 108.153f, 0.0f},
    {70.886589f, -2874.335449f, 116.675f, 0.0f}
};

class npc_00x09hl : public CreatureScript
{
public:
    npc_00x09hl() : CreatureScript("npc_00x09hl") { }

    bool OnQuestAccept(Player* player, Creature* creature, const Quest* quest) override
    {
        if (quest->GetQuestId() == QUEST_RESQUE_OOX_09)
        {
            creature->SetStandState(UNIT_STAND_STATE_STAND);

            if (player->GetTeam() == ALLIANCE)
                creature->SetFaction(FACTION_ESCORTEE_A);
            else if (player->GetTeam() == HORDE)
                creature->SetFaction(FACTION_ESCORTEE_H);

            creature->AI()->Talk(SAY_OOX_START, player);

            if (npc_00x09hlAI* pEscortAI = CAST_AI(npc_00x09hl::npc_00x09hlAI, creature->AI()))
                pEscortAI->Start(false, player->GetGUID(), quest);
        }
        return true;
    }

    CreatureAI* GetAI(Creature* creature) const override
    {
        return new npc_00x09hlAI(creature);
    }

    struct npc_00x09hlAI : public EscortAI
    {
        npc_00x09hlAI(Creature* creature) : EscortAI(creature) { }

        void Reset() override { }

        void WaypointReached(uint32 waypointId, uint32 pathId) override
        {
            switch (waypointId)
            {
                case 26:
                    Talk(SAY_OOX_AMBUSH);
                    break;
                case 43:
                    Talk(SAY_OOX_AMBUSH);
                    break;
                case 64:
                    Talk(SAY_OOX_END);
                    if (Player* player = GetPlayerForEscort())
                        player->GroupEventHappens(QUEST_RESQUE_OOX_09, me);
                    break;
            }
        }

        void WaypointStart(uint32 uiPointId) override
        {
            switch (uiPointId)
            {
                case 27:
                    for (uint8 i = 0; i < 3; ++i)
                    {
                        const Position src = {147.927444f, -3851.513428f, 130.893f, 0};
                        Position dst = me->GetRandomPoint(src, 7.0f);
                        DoSummon(NPC_MARAUDING_OWL, dst, 25000ms, TEMPSUMMON_CORPSE_TIMED_DESPAWN);
                    }
                    break;
                case 44:
                    for (uint8 i = 0; i < 3; ++i)
                    {
                        const Position src = {-141.151581f, -4291.213867f, 120.130f, 0};
                        Position dst = me->GetRandomPoint(src, 7.0f);
                        me->SummonCreature(NPC_VILE_AMBUSHER, dst, TEMPSUMMON_CORPSE_TIMED_DESPAWN, 25000ms);
                    }
                    break;
            }
        }

        void JustEngagedWith(Unit* who) override
        {
            if (who->GetEntry() == NPC_MARAUDING_OWL || who->GetEntry() == NPC_VILE_AMBUSHER)
                return;

            Talk(SAY_OOX_AGGRO);
        }

        void JustSummoned(Creature* summoned) override
        {
            summoned->GetMotionMaster()->MovePoint(0, me->GetPositionX(), me->GetPositionY(), me->GetPositionZ());
        }
    };
};

class npc_rinji : public CreatureScript
{
public:
    npc_rinji() : CreatureScript("npc_rinji") { }

    bool OnQuestAccept(Player* player, Creature* creature, Quest const* quest) override
    {
        if (quest->GetQuestId() != QUEST_RINJI_IS_TRAPPED)
            return true;

        if (GameObject* cage = creature->FindNearestGameObject(GO_RINJIS_CAGE, INTERACTION_DISTANCE))
            cage->UseDoorOrButton();

        if (EscortAI* escortAI = dynamic_cast<EscortAI*>(creature->AI()))
        {
            escortAI->SetRun(false);
            escortAI->Start(false, player->GetGUID(), quest);
        }

        return true;
    }

    struct npc_rinjiAI : public EscortAI
    {
        explicit npc_rinjiAI(Creature* creature) : EscortAI(creature), _postEventCount(0), _postEventTimer(3000), _spawnIndex(0), _spokeToOutrunner(false) { }

        void Reset() override
        {
            _postEventCount = 0;
            _postEventTimer = 3000;
            _spawnIndex = 0;
            _spokeToOutrunner = false;
        }

        void JustEngagedWith(Unit* who) override
        {
            if (!HasEscortState(STATE_ESCORT_ESCORTING))
                return;

            if (who->GetEntry() == NPC_OUTRUNNER && !_spokeToOutrunner)
            {
                if (Creature* outrunner = who->ToCreature())
                    outrunner->AI()->Talk(0);
                _spokeToOutrunner = true;
            }

            if (urand(0, 3) == 0)
                Talk(1);
        }

        void WaypointReached(uint32 pointId, uint32 pathId) override
        {
            switch (pointId)
            {
                case 1:
                    Talk(0);
                    break;
                case 7:
                    SpawnAmbush(0);
                    break;
                case 13:
                    SpawnAmbush(1);
                    break;
                case 17:
                    Talk(2);
                    if (Player* player = GetPlayerForEscort())
                        player->GroupEventHappens(QUEST_RINJI_IS_TRAPPED, me);
                    SetRun(true);
                    _postEventCount = 1;
                    break;
            }
        }

        void JustSummoned(Creature* summoned) override
        {
            me->SetWalk(false);
            Position const& destination = RinjiAmbushMoveTo[_spawnIndex];
            summoned->GetMotionMaster()->MovePoint(0, destination);
        }

        void UpdateEscortAI(uint32 diff) override
        {
            if (!UpdateVictim())
            {
                if (HasEscortState(STATE_ESCORT_ESCORTING) && _postEventCount)
                {
                    if (_postEventTimer <= diff)
                    {
                        _postEventTimer = 3000;
                        if (!GetPlayerForEscort())
                        {
                            me->DespawnOrUnsummon();
                            return;
                        }

                        Talk(_postEventCount == 1 ? 3 : 4);
                        _postEventCount = _postEventCount == 1 ? 2 : 0;
                    }
                    else
                        _postEventTimer -= diff;
                }
                return;
            }

            DoMeleeAttackIfReady();
        }

    private:
        void SpawnAmbush(uint8 spawnIndex)
        {
            _spawnIndex = spawnIndex;
            Position const& spawn = RinjiAmbushSpawn[_spawnIndex];
            me->SummonCreature(NPC_RANGER, spawn, TEMPSUMMON_TIMED_OR_CORPSE_DESPAWN, 60000ms);
            me->SummonCreature(NPC_OUTRUNNER, spawn, TEMPSUMMON_TIMED_OR_CORPSE_DESPAWN, 60000ms);
            me->SummonCreature(NPC_OUTRUNNER, spawn, TEMPSUMMON_TIMED_OR_CORPSE_DESPAWN, 60000ms);
        }

        uint8 _postEventCount;
        uint32 _postEventTimer;
        uint8 _spawnIndex;
        bool _spokeToOutrunner;
    };

    CreatureAI* GetAI(Creature* creature) const override
    {
        return new npc_rinjiAI(creature);
    }
};

void AddSC_hinterlands()
{
    new npc_00x09hl();
    new npc_rinji();
}
