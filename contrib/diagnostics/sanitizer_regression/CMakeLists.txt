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
add_test(NAME spell_loot_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/spell_loot_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(spell_loot_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME spell_power_cost_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/spell_power_cost_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(spell_power_cost_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME gilneas_stagecoach_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/gilneas_stagecoach_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(gilneas_stagecoach_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME vehicle_condition_registry_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/vehicle_condition_registry_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
add_test(NAME movement_path_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/movement_path_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(movement_path_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME navigation_recovery_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/navigation_recovery_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(navigation_recovery_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME battleground_test_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/battleground_test_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(battleground_test_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME combat_removal_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/combat_removal_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(combat_removal_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME battleground_group_lifecycle_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/battleground_group_lifecycle_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(battleground_group_lifecycle_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME battleground_starting_area_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/battleground_starting_area_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(battleground_starting_area_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME playerbot_bg_bracket_distribution_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/playerbot_bg_bracket_distribution_regression.py ${LOA_SOURCE_DIR})
add_test(NAME battleground_resurrection_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/battleground_resurrection_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(battleground_resurrection_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME path_query_budget_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/path_query_budget_regression.py ${LOA_SOURCE_DIR} ${CMAKE_CXX_COMPILER})
set_tests_properties(path_query_budget_regression PROPERTIES ENVIRONMENT "UBSAN_OPTIONS=halt_on_error=1;ASAN_OPTIONS=halt_on_error=1:detect_leaks=1")
add_test(NAME configuration_contract_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/configuration_contract_regression.py ${LOA_SOURCE_DIR})
add_test(NAME botlife_scaffold_regression COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/botlife_scaffold_regression.py ${LOA_SOURCE_DIR})
