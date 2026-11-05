# This file is part of the TrinityCore Project. See AUTHORS file for Copyright information
#
# This file is free software; as a special exception the author gives
# unlimited permission to copy and/or distribute it, with or without
# modifications, as long as this notice is preserved.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY, to the extent permitted by law; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.


# basic packagesearching and setup
# (further support will be needed, this is a preliminary release!)
find_package(OpenSSL 1.1 REQUIRED COMPONENTS Crypto SSL)

set(LOA_OPENSSL_VERSION "${OpenSSL_VERSION}")
if(NOT LOA_OPENSSL_VERSION)
  # FindOpenSSL used the upper-case result variable before CMake 4.2.
  set(LOA_OPENSSL_VERSION "${OPENSSL_VERSION}")
endif()

set(OPENSSL_VERSION_SUPPORTED FALSE)
if((LOA_OPENSSL_VERSION VERSION_GREATER_EQUAL "1.1.1" AND LOA_OPENSSL_VERSION VERSION_LESS "1.2.0") OR
   (LOA_OPENSSL_VERSION VERSION_GREATER_EQUAL "3.0.0" AND LOA_OPENSSL_VERSION VERSION_LESS "3.6.0"))
  set(OPENSSL_VERSION_SUPPORTED TRUE)
endif()

if(NOT OPENSSL_VERSION_SUPPORTED)
  message(FATAL_ERROR
    "Unsupported OpenSSL ${LOA_OPENSSL_VERSION}. Supported versions are 1.1.1 and 3.0.x through 3.5.x.")
endif()

add_library(openssl INTERFACE)

target_link_libraries(openssl
  INTERFACE
    OpenSSL::Crypto
    OpenSSL::SSL)
