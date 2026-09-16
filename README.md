**Mists of Pandaria 5.4.8 Build 18414**

Discord link: https://discord.gg/byBCHbwJEg

Client exe files" https://mega.nz/file/xUJDkIDA#I3TMdPymMw8ISNwIUgSaXLl5oHJHYFxAKyPNMXUQjgY

## Requirements
+ Platform: Linux, Windows or Mac
+ AMD64 or AArch64 CPU architecture
+ MySQL = 5.7 / 8.0-8.1
+ CMake ≥ 3.27.2 
+ OpenSSL = 1.1.1 / 3.0-3.1.1 (3.2.0 not supported) (MySQL >= 8.0.33)
+ Boost ≥ 1.85.0_msvc 14.3 x64 / 1.81 above Linux
+ Windows SDK version 10.0.22621
+ MS Visual Studio (Community) ≥ 16.4 (2019) (Desktop) (Not previews) 
+ GCC >= 13.0, Clang >= 12.0 

## Player bots
Playerbots is in a early stage of developpement, you may encounter bug crash and other unexpected issues.
Its HIGHLY recommanded to disable ELUNA with bot enable.

Few thing to get it working beside importing databases:
+ copy playerbots.conf into your build dir directory or where your executables are
+ you MUST have enUS dbc in order to make bots functionnal
+ add to your worldconf the following settings
	-> PlayerbotsDatabaseInfo = "127.0.0.1;3306;root;root;mop_playerbots"
	-> PlayerbotsDatabase.WorkerThreads     = 1
	-> PlayerbotsDatabase.SynchThreads     = 1
	-> Logger.playerbots=3,Console Server
+ the first start may take times, be patient let everything load and randomize


## Compilation & Testing Instructions

### Compilation (Linux)
1. Install requirements (e.g., GCC, CMake, OpenSSL, Boost, libmysqlclient-dev).
2. Create a build directory and run CMake:
   ```bash
   mkdir build && cd build
   cmake ../ -DWITH_WARNINGS=1
   ```
3. Compile the code using `make`:
   ```bash
   make -j$(nproc)
   ```
4. The compiled executables (like `worldserver`) will be located in `build/src/server/worldserver/`.

### Testing Playerbots
1. Ensure the MySQL server is running.
2. Import the necessary game databases and playerbot databases (`mop_playerbots`).
3. Modify your `worldserver.conf` and copy `playerbots.conf` to the directory with your executables as described in the requirements above.
4. Launch the `worldserver` executable.
5. In the server console or in-game, you can check playerbots using standard bot commands (or simply observe starting zones to verify they are equipping items and starting at level 5, unless properly configured otherwise).


## Copyright
License: GPL 2.0

Read file [COPYING](COPYING.md)

## Authors &amp; Contributors
Read file [THANKS](THANKS.md)

## Build Status
[![windows-build](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/windows-build-release.yml/badge.svg?branch=master)](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/windows-build-release.yml)
[![linux-gcc-build](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/linux_gcc.yml/badge.svg?branch=master)](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/actions/workflows/linux_gcc.yml)

<a href="https://scan.coverity.com/projects/legends-of-azeroth-mop">
  <img alt="Coverity Scan Build Status"
       src="https://scan.coverity.com/projects/26941/badge.svg"/>
</a>
<a href="https://scan.coverity.com/projects/legends-of-azeroth-mop">
  <img alt="Coverity Scan Build Status"
       src="https://img.shields.io/coverity/scan/26941.svg"/>
</a>
