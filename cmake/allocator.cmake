# Keep allocator interception at executable scope, not in shared core archives.
string(TOUPPER "${ALLOCATOR}" allocator_requested)
if(NOT allocator_requested MATCHES "^(AUTO|SYSTEM|MIMALLOC)$")
  message(FATAL_ERROR "ALLOCATOR must be AUTO, SYSTEM or MIMALLOC")
endif()

set(allocator_sanitized ${WITH_SANITIZER})
foreach(flag_variable CMAKE_C_FLAGS CMAKE_CXX_FLAGS CMAKE_EXE_LINKER_FLAGS
    CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
    CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
    CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL)
  if("${${flag_variable}}" MATCHES "-fsanitize=")
    set(allocator_sanitized ON)
  endif()
endforeach()

if(NOJEM)
  message(STATUS "NOJEM is deprecated; using the SYSTEM allocator")
  if(allocator_requested STREQUAL "MIMALLOC")
    message(FATAL_ERROR "NOJEM conflicts with ALLOCATOR=MIMALLOC; remove NOJEM")
  endif()
  set(allocator_requested SYSTEM)
endif()

if(allocator_requested STREQUAL "AUTO")
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT allocator_sanitized)
    set(allocator_selected MIMALLOC)
  else()
    set(allocator_selected SYSTEM)
  endif()
else()
  set(allocator_selected ${allocator_requested})
endif()

add_library(server_allocator INTERFACE)
if(allocator_selected STREQUAL "MIMALLOC")
  if(CMAKE_VERSION VERSION_LESS 3.18)
    message(FATAL_ERROR "mimalloc requires CMake >= 3.18; upgrade CMake or use ALLOCATOR=SYSTEM")
  endif()
  if(allocator_sanitized)
    message(FATAL_ERROR "Sanitizer builds require ALLOCATOR=SYSTEM (or AUTO)")
  endif()
  if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "MIMALLOC override is currently validated only for Linux; use SYSTEM")
  endif()
  include(FetchContent)
  if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
  endif()
  set(MI_BUILD_SHARED OFF CACHE BOOL "" FORCE)
  # Upstream's object-copy target also depends on its static target.
  set(MI_BUILD_STATIC ON CACHE BOOL "" FORCE)
  set(MI_BUILD_OBJECT ON CACHE BOOL "" FORCE)
  set(MI_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(MI_OVERRIDE ON CACHE BOOL "" FORCE)
  set(MI_OPT_ARCH OFF CACHE STRING "" FORCE)
  set(MI_GUARDED OFF CACHE STRING "" FORCE)
  set(MI_STATS OFF CACHE STRING "" FORCE)
  set(MI_PROFILE OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(loa_mimalloc
    URL https://codeload.github.com/microsoft/mimalloc/tar.gz/refs/tags/v3.5.3
    URL_HASH SHA256=3b4a15153a59905995f7070296ed604bb5ccc00cabb8b93446931aff77224d47)
  FetchContent_MakeAvailable(loa_mimalloc)
  # The object precedes archives; an archive-only link can silently lose overrides.
  target_link_libraries(server_allocator INTERFACE mimalloc-obj $<TARGET_OBJECTS:mimalloc-obj>)
  # These are PUBLIC on the upstream static target, but not on its object target.
  target_link_libraries(server_allocator INTERFACE pthread rt atomic)
endif()
message(STATUS "Server allocator: ${allocator_selected}")
