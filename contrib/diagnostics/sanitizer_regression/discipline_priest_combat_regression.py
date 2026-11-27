#!/usr/bin/env python3
"""Exercise the production Discipline default actions as group and master change."""
from pathlib import Path
import subprocess
import sys
import tempfile


root, compiler = Path(sys.argv[1]), sys.argv[2]
source = (root / 'modules/mod_playerbots/src/strategy/Classes/priest/HealPriestStrategy.cpp').read_text()
start = source.index('NextAction** HealPriestStrategy::getDefaultActions()')
method = source[start:source.index('\n}', start) + 2]

with tempfile.TemporaryDirectory(prefix='discipline-priest-combat-') as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    cpp.write_text(r'''
#include <cassert>
#include <string_view>

struct NextAction
{
    std::string_view name;
    float relevance;

    template <typename... Actions>
    static NextAction** array(int, Actions... actions)
    {
        return new NextAction*[sizeof...(actions)]{actions...};
    }
};

constexpr float ACTION_DEFAULT = 5.0f;

struct Player
{
    bool grouped = false;
    bool GetGroup() const { return grouped; }
};

struct AI
{
    Player bot;
    Player* master = nullptr;
    Player* GetMaster() const { return master; }
    Player* GetBot() { return &bot; }
};

struct HealPriestStrategy
{
    AI* botAI;
    NextAction** getDefaultActions();
};
''' + method + r'''

void check(HealPriestStrategy& strategy, bool solo)
{
    NextAction** actions = strategy.getDefaultActions();
    if (solo)
    {
        assert(actions[0]->name == "smite");
        assert(actions[0]->relevance > actions[1]->relevance);
    }
    assert(actions[solo]->name == "shoot" && actions[solo + 1] == nullptr);
    for (auto action = actions; *action; ++action)
        delete *action;
    delete[] actions;
}

int main()
{
    AI ai;
    HealPriestStrategy strategy{&ai};
    check(strategy, true);
    ai.bot.grouped = true;
    check(strategy, false);
    ai.bot.grouped = false;
    Player master;
    ai.master = &master;
    check(strategy, false);
    ai.master = nullptr;
    check(strategy, true);
}
''')
    subprocess.run([compiler, '-std=c++20', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-fno-pie', '-no-pie', str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
