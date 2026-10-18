#pragma once

#include "Player.h"

class PlayerbotAI
{
public:
    Player* bot;
    bool playerMaster = false;
    Player* GetBot() const { return bot; }
    bool HasRealPlayerMaster() const { return playerMaster; }
};
