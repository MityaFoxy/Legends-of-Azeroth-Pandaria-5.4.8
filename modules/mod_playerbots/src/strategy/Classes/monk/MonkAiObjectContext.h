/*
 * Copyright (C) 2026 Legends of Azeroth Pandaria Project.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 */

#ifndef _PLAYERBOT_MONKAIOBJECTCONTEXT_H
#define _PLAYERBOT_MONKAIOBJECTCONTEXT_H

#include "AiObjectContext.h"

class PlayerbotAI;

class MonkAiObjectContext : public AiObjectContext
{
public:
    MonkAiObjectContext(PlayerbotAI* botAI);
};

#endif
