<div align="center">

# Legends of Azeroth — Pandaria 5.4.8

**A maintained C++20 development fork for Mists of Pandaria 5.4.8 (build 18414)**

[![Linux GCC](https://github.com/MityaFoxy/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/linux_gcc.yml/badge.svg?branch=master)](https://github.com/MityaFoxy/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/linux_gcc.yml)
[![Windows](https://github.com/MityaFoxy/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/windows-build-release.yml/badge.svg?branch=master)](https://github.com/MityaFoxy/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/windows-build-release.yml)
[![C++20](https://img.shields.io/badge/C%2B%2B-20-00599C?logo=cplusplus)](CMakeLists.txt)
[![License: GPL v2](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](COPYING.md)

<img src="docs/assets/pandaria-horizon.jpg" alt="Pandaria mountain landscape" width="100%">

</div>

## About this fork

This is a personal, actively maintained server-development branch for the **Mists of Pandaria 5.4.8 / build 18414** client. It keeps a modern, reproducible C++20 build while concentrating on practical server stability and a lively long-running world.

### Focus

- **Playerbot-oriented world** — the project is configured and tested with player bots in mind, including the separate bot database and bot-specific runtime settings.
- **Stability first** — extra null-safety fixes from static analysis reduce avoidable server crashes in core and encounter scripts.
- **Modern toolchain** — C++20, CMake, continuous builds for Linux, Windows and Apple Silicon macOS.
- **Development-friendly** — optional modules, Lua scripting, map tools and clear build switches make experimentation less painful.
- **Upstream-aware** — changes are kept as a focused layer so functional updates and fixes can be integrated deliberately.

<div align="center">
  <img src="docs/assets/mop-panda-emblem.png" alt="Mists of Pandaria panda emblem" width="260">
</div>

> This repository contains server source code only. A compatible **enUS Mists of Pandaria 5.4.8 (build 18414)** client and extracted map data are required to play.

## Requirements

| Component | Supported / tested |
| --- | --- |
| Operating system | Linux, Windows, or macOS (AMD64; macOS also AArch64) |
| C++ standard | C++20 |
| CMake | **3.16+** |
| Compiler | GCC **13+**, Clang **12+**, or Visual Studio **2019 16.4+** |
| Database | MySQL **5.7** or **8.0–8.1** |
| OpenSSL | **1.1.1** or **3.0–3.1.1**; OpenSSL 3.2 is not supported with newer MySQL |
| Boost | **1.85+** recommended |
| Windows SDK | 10.0.22621 or newer recommended |
| Client data | MoP 5.4.8 build 18414; **enUS DBC** is required for player bots |

## Build

Clone with submodules, then configure an out-of-source build:

```bash
git clone --recurse-submodules https://github.com/MityaFoxy/Legends-of-Azeroth-Pandaria-5.4.8.git
cd Legends-of-Azeroth-Pandaria-5.4.8

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

For a development build:

```bash
cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug --parallel
```

### Useful CMake options

| Option | Default | Purpose |
| --- | --- | --- |
| `-DPLAYERBOTS=1` | ON | Build player-bot support |
| `-DELUNA=1` | ON | Enable Lua scripting engine |
| `-DTOOLS=1` | OFF | Build map, vmap and mmap extractors |
| `-DSCRIPTS=1` | ON | Build custom C++ scripts |
| `-DCOREPCH=0 -DSCRIPTPCH=0` | ON | Disable PCH when it helps incremental iteration |
| `-DBUILD_DEPLOY=1` | ON on Unix | Produce deployable Unix layout |

> When running player bots, disabling Eluna is strongly recommended: `-DELUNA=0`.

## Database and first launch

1. Create and import the base **auth**, **characters**, and **world** databases from `sql/base/`.
2. Apply dated updates from `sql/updates/` in order.
3. Configure database access in `authserver.conf` and `worldserver.conf`.
4. Run the extractors (`-DTOOLS=1`) against your compatible client, then place the generated maps, vmaps and mmaps beside the server data.
5. Start `authserver`, then `worldserver`.

## Player bots

Player bots need one additional database and configuration step:

1. Import the playerbots database as `mop_playerbots`.
2. Copy `playerbots.conf` next to the server executables.
3. In `worldserver.conf`, set:

```ini
PlayerbotsDatabaseInfo = "127.0.0.1;3306;root;root;mop_playerbots"
PlayerbotsDatabase.WorkerThreads = 1
PlayerbotsDatabase.SynchThreads = 1
Logger.playerbots = 3,Console Server
```

The first startup may take noticeably longer while bot data is initialized and randomized. Let it finish before judging runtime behavior.

## Project layout

| Path | Contents |
| --- | --- |
| `src/server/game/` | Core gameplay: entities, maps, spells, quests, combat and AI |
| `src/server/authserver/` / `worldserver/` | Authentication and world executables |
| `src/server/scripts/` | C++ content scripts |
| `modules/` | Optional core modules |
| `src/tools/` | Map, vmap and mmap extraction tools |
| `sql/base/` / `sql/updates/` | Base schemas and incremental database updates |
| `contrib/lua_scripts/` | Runtime Eluna Lua scripts |
| `AGENTS.md` | Working notes for contributors and coding agents |

## Contributing

Please keep changes focused, compile-tested, and compatible with the configured C++20 toolchain. Follow [`doc/code_standards.md`](doc/code_standards.md) and see [`AGENTS.md`](AGENTS.md) for build and development notes.

## License

This project is distributed under **GPL-2.0**. See [`COPYING.md`](COPYING.md).

## Credits

Thanks to every open-source contributor whose work forms the foundation of this server project. See [`THANKS.md`](THANKS.md) for the full credits list.
