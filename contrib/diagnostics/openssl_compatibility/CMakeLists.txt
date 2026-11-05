add_executable(openssl_compatibility
  main.cpp)

target_link_libraries(openssl_compatibility
  PRIVATE
    common)

set_target_properties(openssl_compatibility PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
