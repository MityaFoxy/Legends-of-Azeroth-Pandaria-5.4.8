/*
* This file is part of the Pandaria 5.4.8 Project. See THANKS file for Copyright information
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

#include "ScriptMgr.h"
#include "ScriptedCreature.h"
#include "ScriptedEscortAI.h"
#include "Player.h"

namespace
{
enum GalenGoodward
{
    QUEST_GALENS_ESCAPE = 1393,
    GO_GALENS_CAGE = 37118
};

class npc_galen_goodward : public CreatureScript
{
public:
    npc_galen_goodward() : CreatureScript("npc_galen_goodward") { }

    bool OnQuestAccept(Player* player, Creature* creature, Quest const* quest) override
    {
        if (quest->GetQuestId() != QUEST_GALENS_ESCAPE)
            return true;

        if (EscortAI* escortAI = dynamic_cast<EscortAI*>(creature->AI()))
        {
            escortAI->SetRun(false);
            escortAI->Start(false, player->GetGUID(), quest);
            creature->SetFaction(FACTION_ESCORT_N_NEUTRAL_ACTIVE);
            creature->AI()->Talk(1);
        }

        return true;
    }

    struct npc_galen_goodwardAI : public EscortAI
    {
        explicit npc_galen_goodwardAI(Creature* creature) : EscortAI(creature), _periodicSayTimer(6000) { }

        void Reset() override
        {
            _periodicSayTimer = 6000;
        }

        void JustEngagedWith(Unit* who) override
        {
            if (HasEscortState(STATE_ESCORT_ESCORTING))
                Talk(2, who);
        }

        void WaypointStart(uint32 pointId) override
        {
            if (pointId == 0)
            {
                if (GameObject* cage = me->FindNearestGameObject(GO_GALENS_CAGE, INTERACTION_DISTANCE))
                    cage->UseDoorOrButton();
            }
            else if (pointId == 21)
                Talk(5);
        }

        void WaypointReached(uint32 pointId, uint32 pathId) override
        {
            if (pointId == 0)
            {
                if (GameObject* cage = me->FindNearestGameObject(GO_GALENS_CAGE, INTERACTION_DISTANCE))
                    cage->ResetDoorOrButton();
            }
            else if (pointId == 20)
            {
                if (Player* player = GetPlayerForEscort())
                {
                    me->SetFacingToObject(player);
                    Talk(3, player);
                    Talk(4, player);
                    player->GroupEventHappens(QUEST_GALENS_ESCAPE, me);
                }

                SetRun(true);
            }
        }

        void UpdateEscortAI(uint32 diff) override
        {
            if (_periodicSayTimer <= diff)
            {
                if (HasEscortState(STATE_ESCORT_NONE))
                    Talk(0);
                _periodicSayTimer = 6000;
            }
            else
                _periodicSayTimer -= diff;

            if (UpdateVictim())
                DoMeleeAttackIfReady();
        }

    private:
        uint32 _periodicSayTimer;
    };

    CreatureAI* GetAI(Creature* creature) const override
    {
        return new npc_galen_goodwardAI(creature);
    }
};
}

void AddSC_swamp_of_sorrows()
{
    new npc_galen_goodward();
}
