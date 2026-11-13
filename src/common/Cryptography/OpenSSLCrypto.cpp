/*
* This file is part of the Legends of Azeroth Pandaria Project. See THANKS file for Copyright information
*
* This program is free software; you can redistribute it and/or modify it
* under the terms of the GNU General Public License as published by the
* Free Software Foundation; either version 2 of the License, or (at your
* option) any later version.
*
* This program is distributed in the hope that it will be useful, but WITHOUT
* ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
* FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
* more details.
*
* You should have received a copy of the GNU General Public License along
* with this program. If not, see <http://www.gnu.org/licenses/>.
*/

#include <OpenSSLCrypto.h>
#include "Errors.h"
#include <openssl/crypto.h>

#if defined(OPENSSL_VERSION_NUMBER) && OPENSSL_VERSION_NUMBER < 0x1010000fL
#include <vector>
#include <thread>
#include <mutex>

std::vector<std::mutex*> cryptoLocks;

static void lockingCallback(int mode, int type, char const* /*file*/, int /*line*/)
{
    if (mode & CRYPTO_LOCK)
        cryptoLocks[type]->lock();
    else
        cryptoLocks[type]->unlock();
}

static void threadIdCallback(CRYPTO_THREADID * id)
{
    (void)id;
    CRYPTO_THREADID_set_numeric(id, std::hash<std::thread::id>()(std::this_thread::get_id()));
}
#elif OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/evp.h>
#include <openssl/provider.h>

namespace
{
OSSL_PROVIDER* LegacyProvider = nullptr;
OSSL_PROVIDER* DefaultProvider = nullptr;
}
#endif

void OpenSSLCrypto::threadsSetup([[maybe_unused]] boost::filesystem::path const& providerModulePath)
{
#if defined(OPENSSL_VERSION_NUMBER) && OPENSSL_VERSION_NUMBER < 0x1010000fL
    cryptoLocks.resize(CRYPTO_num_locks());
    for(int i = 0 ; i < CRYPTO_num_locks(); ++i)
    {
        cryptoLocks[i] = new std::mutex();
    }

    (void)&threadIdCallback;
    CRYPTO_THREADID_set_callback(threadIdCallback);

    (void)&lockingCallback;
    CRYPTO_set_locking_callback(lockingCallback);
#elif OPENSSL_VERSION_NUMBER >= 0x30000000L
#if TRINITY_PLATFORM == TRINITY_PLATFORM_WINDOWS
    OSSL_PROVIDER_set_default_search_path(nullptr, providerModulePath.string().c_str());
#endif
    LegacyProvider = OSSL_PROVIDER_load(nullptr, "legacy");
    WPFatal(LegacyProvider, "OpenSSL legacy provider could not be loaded. RC4 is required by the MoP 5.4.8 session protocol.");
    DefaultProvider = OSSL_PROVIDER_load(nullptr, "default");
    WPFatal(DefaultProvider, "OpenSSL default provider could not be loaded.");

    EVP_CIPHER* rc4 = EVP_CIPHER_fetch(nullptr, "RC4", "provider=legacy");
    WPFatal(rc4, "OpenSSL legacy provider does not expose RC4, which is required by the MoP 5.4.8 session protocol.");
    EVP_CIPHER_free(rc4);
#endif
}

void OpenSSLCrypto::threadsCleanup()
{
#if defined(OPENSSL_VERSION_NUMBER) && OPENSSL_VERSION_NUMBER < 0x1010000fL
    CRYPTO_set_locking_callback(nullptr);
    CRYPTO_THREADID_set_callback(nullptr);
    for(int i = 0 ; i < CRYPTO_num_locks(); ++i)
    {
        delete cryptoLocks[i];
    }
    cryptoLocks.resize(0);
#elif OPENSSL_VERSION_NUMBER >= 0x30000000L
    if (LegacyProvider)
    {
        OSSL_PROVIDER_unload(LegacyProvider);
        LegacyProvider = nullptr;
    }
    if (DefaultProvider)
    {
        OSSL_PROVIDER_unload(DefaultProvider);
        DefaultProvider = nullptr;
    }
    OSSL_PROVIDER_set_default_search_path(nullptr, nullptr);
#endif
}
