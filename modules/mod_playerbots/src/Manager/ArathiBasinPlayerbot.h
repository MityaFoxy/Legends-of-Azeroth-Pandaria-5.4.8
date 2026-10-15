#pragma once

#include "Common.h"

#include <string>

class PlayerbotAI;

namespace ArathiBasinPlayerbot
{
    struct State
    {
        uint32 objectiveInstance = 0;
        uint32 team = 0;
        uint32 lastObjectiveReview = 0;
        uint32 approachStarted = 0;
        uint32 approachRouteFailureStarted = 0;
        uint32 approachBanner = 0;
        uint32 lastSeparation = 0;
        uint32 lastBannerLog = 0;
        uint32 lastQueueRequest = 0;
        uint8 objective = 0;
        uint8 approachVariant = 0;
        uint8 approachFailures = 0;
        bool objectiveSet = false;
        bool approachSet = false;
        bool wasAlive = false;
        bool bannerLogged = false;
        bool queueRequested = false;
        float approachX = 0.0f;
        float approachY = 0.0f;
        float approachZ = 0.0f;
        std::string bannerPhase;
    };

    // World-thread lifecycle for ordinary autonomous random bots. It only
    // queues/accepts/leaves; battleground rules remain authoritative.
    void Update(uint32 diff);

    // Map-thread Arathi Basin objective behavior shared by ordinary bots and
    // the optional load-test population.
    bool DoNextAction(PlayerbotAI* ai);
}
