#ifndef _PLAYERBOT_DRUIDCONTROLACTIONS_H
#define _PLAYERBOT_DRUIDCONTROLACTIONS_H

#include "GenericSpellActions.h"
#include "Trigger.h"

// The existing group CC icon is the assignment. No automatic CC target policy
// is introduced while the shared cc-target Values remain unimplemented.
Unit* SelectDruidCcTarget(PlayerbotAI* ai, uint32 spellId);
Unit* SelectDruidBashTarget(PlayerbotAI* ai, bool healer);

class DruidCcAction : public CastSpellAction
{
public:
    DruidCcAction(PlayerbotAI* ai, std::string const spell, uint32 id, std::string const alias)
        : CastSpellAction(ai, spell), id(id), alias(alias) {}
    std::string const getName() override { return alias; }
    Unit* GetTarget() override;
    bool isUseful() override;
    bool isPossible() override;
    bool Execute(Event event) override;
    NextAction** getPrerequisites() override;

private:
    uint32 id;
    std::string alias;
};

class DruidBashAction : public CastSpellAction
{
public:
    DruidBashAction(PlayerbotAI* ai, bool healer = false)
        : CastSpellAction(ai, "mighty bash"), healer(healer) {}
    std::string const getName() override { return healer ? "bash on enemy healer" : "bash"; }
    Unit* GetTarget() override;
    bool isUseful() override;
    bool isPossible() override;
    bool Execute(Event event) override;

private:
    bool healer;
};

class DruidControlTrigger : public Trigger
{
public:
    DruidControlTrigger(PlayerbotAI* ai, std::string const name, std::string const action)
        : Trigger(ai, name), action(action) {}
    bool IsActive() override;

private:
    std::string action;
};

class DruidNaturesSwiftnessTrigger : public Trigger
{
public:
    DruidNaturesSwiftnessTrigger(PlayerbotAI* ai) : Trigger(ai, "nature's swiftness") {}
    bool IsActive() override;
};

#endif
