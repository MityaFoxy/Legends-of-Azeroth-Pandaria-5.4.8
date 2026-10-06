# Server allocator

The bundled jemalloc is no longer built or linked. Its historical source directory
is retained for provenance; it has no active CMake references.

`-DALLOCATOR=AUTO` selects mimalloc 3.5.3 on Linux without sanitizer flags and
the system allocator elsewhere. `SYSTEM` explicitly opts out of custom allocation;
`MIMALLOC` explicitly enables the validated Linux integration. Invalid values and
explicit mimalloc with sanitizer flags fail configuration. The deprecated
`NOJEM=ON` maps to SYSTEM; remove it when selecting MIMALLOC.

mimalloc sources are fetched from the official versioned archive and checked
against SHA-256. The first configuration needs network access; offline builds can
use `FETCHCONTENT_SOURCE_DIR_LOA_MIMALLOC` with an independently verified source
tree. The override object is linked into each server executable before archives,
not hidden in a core archive. Normal launch commands need no `LD_PRELOAD` and no
additional mimalloc runtime library. The existing `NO_BUFFERPOOL` core policy is
preserved independently of allocator selection.

Verify normal binaries with `nm -g --defined-only`: `malloc` and `mi_malloc` must
both be defined. `MIMALLOC_VERBOSE=1` enables startup confirmation. Static jemalloc
does not appear in ldd, so absence there alone is not sufficient proof.

ASan/UBSan use SYSTEM and their standard allocation interceptors, not mimalloc.
A sanitizer soak validates memory use in core code, not mimalloc interception.
The test workflow therefore separately exercises the mimalloc binary with
25/50/100 bots before the sanitizer run. No speedup is claimed without comparable
workload measurements; allocator replacement does not change database schemas.

Official upstream documentation:
https://microsoft.github.io/mimalloc/overrides.html
https://github.com/microsoft/mimalloc/releases/tag/v3.5.3
