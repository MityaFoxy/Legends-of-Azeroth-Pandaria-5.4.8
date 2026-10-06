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
