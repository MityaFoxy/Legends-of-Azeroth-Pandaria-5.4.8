#pragma once

class WorldSession
{
public:
    bool loggingOut = false;
    bool isLogingOut() const { return loggingOut; }
};
