#!/usr/bin/env python3
"""Guard the first MoP 5.4.8 configuration cleanup contract."""

import pathlib
import re
import sys


root = pathlib.Path(sys.argv[1])
config = (root / "src/server/worldserver/worldserver.conf.dist").read_text()
world = (root / "src/server/game/World/World.cpp").read_text()
world_header = (root / "src/server/game/World/World.h").read_text()
misc_handler = (root / "src/server/game/Handlers/MiscHandler.cpp").read_text()


def has_assignment(key):
    return re.search(rf"^\s*{re.escape(key)}\s*=", config, re.MULTILINE) is not None


dead_keys = (
    "mmap.AllowReuseOfPreviousPathSegments",
    "AuthServer.Process",
    "AuthServer.Command",
    "MapUpdateInterval",
    "Rate.Talent",
    "Arena.AutoDistributePoints",
    "Arena.AutoDistributeInterval",
    "CONFIGSPECPETFEROCITY",
    "CONFIGSPECPETCUNNING",
    "CONFIGSPECPETTENACITY",
    "HEALCONFIGSPECPETFEROCITY",
    "HEALCONFIGSPECPETCUNNING",
    "HEALCONFIGSPECPETTENACITY",
    "Eluna.TraceBack",
)
for key in dead_keys:
    assert not has_assignment(key), f"obsolete configuration assignment returned: {key}"

assert 'GetIntDefault("MaxWhoListReturns", 49)' in world
assert "must be in range 1..49" in world
assert "displaycount < sWorld->getIntConfig(CONFIG_MAX_WHO)" in misc_handler
assert 'GetBoolDefault("Warden.Enabled", true)' in world
assert "m_int_configs[CONFIG_INTERVAL_MAPUPDATE] = 200;" in world
assert "Map updates are fixed at 200 ms" in config

for dead_enum in (
    "CONFIGSPECPETFEROCITY",
    "CONFIGSPECPETCUNNING",
    "CONFIGSPECPETTENACITY",
    "HEALCONFIGSPECPETFEROCITY",
    "HEALCONFIGSPECPETCUNNING",
    "HEALCONFIGSPECPETTENACITY",
):
    assert dead_enum not in world_header, f"obsolete enum returned: {dead_enum}"

for live_pet_key in (
    "CONFIG_SPEC_PET_FEROCITY",
    "CONFIG_SPEC_PET_TENACITY",
    "CONFIG_SPEC_PET_CUNNING",
    "CONFIG_PET_NO_SPEC",
):
    assert has_assignment(live_pet_key), f"live pet balance setting missing: {live_pet_key}"
    assert f'GetFloatDefault("{live_pet_key}", 100.0f)' in world

print("MoP configuration contract passed")
