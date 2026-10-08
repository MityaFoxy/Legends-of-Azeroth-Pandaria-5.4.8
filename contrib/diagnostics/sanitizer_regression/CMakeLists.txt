cmake_minimum_required(VERSION 3.18)
project(loa_sanitizer_regression LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
add_executable(sanitizer_regression main.cpp)
target_include_directories(sanitizer_regression PRIVATE
  ${LOA_SOURCE_DIR}/src/common/Utilities
  ${LOA_SOURCE_DIR}/src/server/game/Entities/Object
  ${LOA_SOURCE_DIR}/dep/recastnavigation/Detour/Include)
target_compile_options(sanitizer_regression PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
target_link_options(sanitizer_regression PRIVATE -fsanitize=address,undefined)
enable_testing()
add_test(NAME sanitizer_regression COMMAND sanitizer_regression)
set_tests_properties(sanitizer_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1")
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME lifecycle_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/lifecycle_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(lifecycle_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1")
add_test(NAME leak_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/leak_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(leak_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME cleanup_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/cleanup_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(cleanup_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME auction_target_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/auction_target_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(auction_target_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME gameobject_owner_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/gameobject_owner_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(gameobject_owner_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME soak_controller_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/soak_controller_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
add_test(NAME bot_behavior_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/bot_behavior_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(bot_behavior_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME map_script_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/map_script_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(map_script_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
