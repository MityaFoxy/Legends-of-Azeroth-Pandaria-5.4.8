# MoP 5.4.8 configuration audit

Target: the local Legends of Azeroth architecture and the 5.4.8 client. A key in
`*.conf.dist` is considered supported only when the current source consumes it;
another emulator is supporting evidence, not authority for local behavior.

## First cleanup batch

| Setting | Finding | Decision |
| --- | --- | --- |
| `Warden.Enabled` | Documented but hardcoded to enabled | Read the setting and preserve the shipped default (`1`) |
| `MaxWhoListReturns` | Documented but hardcoded to `49` | Read it, constrain it to the stable client range `1..49`, and make the loop return no more than the configured count |
| `MapUpdateInterval` | Advertised as `10`, while the core intentionally uses `200` due to mmap instability | Remove the false assignment and document the fixed value |
| `mmap.AllowReuseOfPreviousPathSegments` | The conditional behavior was removed when `PathGenerator` changed from `Unit` to `WorldObject` | Remove the orphaned setting |
| `AuthServer.Process`, `AuthServer.Command` | Their Windows/ACE launcher was removed during the Boost worldserver migration | Remove the orphaned settings |
| `Rate.Talent` | No consumer or rate enum exists; MoP replaced the old talent-point progression | Remove the WotLK-era setting |
| `Arena.AutoDistributePoints`, `Arena.AutoDistributeInterval` | No consumer exists in the current rated-PvP implementation | Remove the orphaned settings |
| old pet damage/healing keys | Never loaded; the active pet damage system uses `CONFIG_SPEC_PET_*` and `CONFIG_PET_NO_SPEC` | Remove the duplicate keys and unused enum entries |
| `Eluna.TraceBack` | Present since the initial Eluna import but never consumed by this integration | Remove the unsupported setting |

The regression `configuration_contract_regression.py` keeps these removed keys
out of the distributed configuration and verifies the two restored switches and
the active pet-balance replacements.

## Evidence

- Local history: `62570817f5a48ce2c802ec4c18e56ef949f23619` added the loose top-level
  settings; `b467cfd99d66adde6d33e9c3c079539facd3da99` removed the mmap reuse
  branch; `3534a67b3d9f847f23cf38bcb5988882f3c191ef` removed the ACE authserver
  launcher.
- [ProjectSkyfire/SkyFire_548 at `aea3c6ed`](https://github.com/ProjectSkyfire/SkyFire_548/tree/aea3c6ed92c14fd55f560fd7cc18d4a8c68799d8)
  confirms that `Warden.Enabled` and `MaxWhoListReturns` are intended runtime
  inputs in the shared 5.4.8 lineage.
- [Blizzard's Mists of Pandaria talent overview](https://worldofwarcraft.blizzard.com/en-us/news/3773320)
  describes the level-based talent choices that replaced rate-scaled talent
  points.

## Deferred work

- Classify the remaining Playerbot keys individually. Absence of an exact
  string is not enough because this module constructs some names dynamically
  and also contains partially ported features.
- Audit undocumented live settings (`StrictVersionCheck`, transfer-mail fields,
  and the arena reward cleanup switch) before adding them to templates.
- Revisit gameplay defaults separately from dead-key cleanup; a supported key
  can still have a WotLK-era value or comment.
