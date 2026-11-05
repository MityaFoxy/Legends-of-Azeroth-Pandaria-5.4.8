/*
* This file is part of the Pandaria 5.4.8 Project. See THANKS file for Copyright information
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

#ifndef TRINITY_HMAC_H
#define TRINITY_HMAC_H

#include "CryptoConstants.h"
#include "CryptoHash.h"
#include "Define.h"
#include "Errors.h"
#include <array>
#include <openssl/opensslv.h>
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/core_names.h>
#include <openssl/params.h>
#endif
#include <string>
#include <string_view>

class BigNumber;

namespace Trinity::Impl
{
    template <GenericHashImpl::HashCreator HashCreator, size_t DigestLength>
    class GenericHMAC
    {
        public:
            static constexpr size_t DIGEST_LENGTH = DigestLength;
            using Digest = std::array<uint8, DIGEST_LENGTH>;

            template <typename Container>
            static Digest GetDigestOf(Container const& seed, uint8 const* data, size_t len)
            {
                GenericHMAC hash(seed);
                hash.UpdateData(data, len);
                hash.Finalize();
                return hash.GetDigest();
            }

            template <typename Container, typename... Ts>
            static auto GetDigestOf(Container const& seed, Ts&&... pack) -> std::enable_if_t<!(std::is_integral_v<std::decay_t<Ts>> || ...), Digest>
            {
                GenericHMAC hash(seed);
                (hash.UpdateData(std::forward<Ts>(pack)), ...);
                hash.Finalize();
                return hash.GetDigest();
            }

            GenericHMAC(uint8 const* seed, size_t len)
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                : _ctx(CreateContext(seed, len))
#else
                : _ctx(GenericHashImpl::MakeCTX()), _key(EVP_PKEY_new_mac_key(EVP_PKEY_HMAC, nullptr, seed, len))
#endif
            {
#if OPENSSL_VERSION_NUMBER < 0x30000000L
                ASSERT(_ctx);
                ASSERT(_key);
                int result = EVP_DigestSignInit(_ctx, nullptr, HashCreator(), nullptr, _key);
                ASSERT(result == 1);
#endif
            }
            template <typename Container>
            GenericHMAC(Container const& container)
                : GenericHMAC(reinterpret_cast<uint8 const*>(std::data(container)), std::size(container)) {}

            GenericHMAC(GenericHMAC const& right)
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                : _ctx(EVP_MAC_CTX_dup(right._ctx)), _digest(right._digest)
#else
                : _ctx(GenericHashImpl::MakeCTX()), _key(nullptr)
#endif
            {
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                ASSERT(_ctx);
#else
                *this = right;
#endif
            }

            GenericHMAC(GenericHMAC&& right) noexcept
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                : _ctx(std::exchange(right._ctx, nullptr)), _digest(std::exchange(right._digest, Digest{})) {}
#else
                : _ctx(std::exchange(right._ctx, nullptr)), _key(std::exchange(right._key, nullptr)),
                  _digest(std::exchange(right._digest, Digest{})) {}
#endif

            ~GenericHMAC()
            {
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                EVP_MAC_CTX_free(_ctx);
#else
                GenericHashImpl::DestroyCTX(_ctx);
                EVP_PKEY_free(_key);
#endif
            }

            GenericHMAC& operator=(GenericHMAC const& right)
            {
                if (this == &right)
                    return *this;

#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                EVP_MAC_CTX* context = EVP_MAC_CTX_dup(right._ctx);
                ASSERT(context);
                EVP_MAC_CTX_free(_ctx);
                _ctx = context;
#else
                EVP_MD_CTX* context = GenericHashImpl::MakeCTX();
                ASSERT(context);
                int result = EVP_MD_CTX_copy_ex(context, right._ctx);
                ASSERT(result == 1);
                result = EVP_PKEY_up_ref(right._key);
                ASSERT(result == 1);
                GenericHashImpl::DestroyCTX(_ctx);
                EVP_PKEY_free(_key);
                _ctx = context;
                _key = right._key;
#endif
                _digest = right._digest;
                return *this;
            }

            GenericHMAC& operator=(GenericHMAC&& right) noexcept
            {
                if (this == &right)
                    return *this;

#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                EVP_MAC_CTX_free(_ctx);
                _ctx = std::exchange(right._ctx, nullptr);
#else
                GenericHashImpl::DestroyCTX(_ctx);
                EVP_PKEY_free(_key);
                _ctx = std::exchange(right._ctx, nullptr);
                _key = std::exchange(right._key, nullptr);
#endif
                _digest = std::exchange(right._digest, Digest{});
                return *this;
            }

            void UpdateData(uint8 const* data, size_t len)
            {
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                int result = EVP_MAC_update(_ctx, data, len);
#else
                int result = EVP_DigestSignUpdate(_ctx, data, len);
#endif
                ASSERT(result == 1);
            }
            void UpdateData(std::string_view str) { UpdateData(reinterpret_cast<uint8 const*>(str.data()), str.size()); }
            void UpdateData(std::string const& str) { UpdateData(std::string_view(str)); } /* explicit overload to avoid using the container template */
            void UpdateData(char const* str) { UpdateData(std::string_view(str)); } /* explicit overload to avoid using the container template */
            template <typename Container>
            void UpdateData(Container const& c)
            {
                UpdateData(reinterpret_cast<uint8 const*>(std::data(c)), std::size(c));
            }

            void Finalize()
            {
                size_t length = DIGEST_LENGTH;
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
                int result = EVP_MAC_final(_ctx, _digest.data(), &length, _digest.size());
#else
                int result = EVP_DigestSignFinal(_ctx, _digest.data(), &length);
#endif
                ASSERT(result == 1);
                ASSERT(length == DIGEST_LENGTH);
            }

            Digest const& GetDigest() const { return _digest; }
        private:
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
            static EVP_MAC_CTX* CreateContext(uint8 const* seed, size_t len)
            {
                EVP_MAC* mac = EVP_MAC_fetch(nullptr, "HMAC", "provider=default");
                ASSERT(mac);
                EVP_MAC_CTX* context = EVP_MAC_CTX_new(mac);
                EVP_MAC_free(mac);
                ASSERT(context);

                char const* digestName = EVP_MD_get0_name(HashCreator());
                OSSL_PARAM params[] =
                {
                    OSSL_PARAM_construct_utf8_string(OSSL_MAC_PARAM_DIGEST, const_cast<char*>(digestName), 0),
                    OSSL_PARAM_construct_end()
                };
                int result = EVP_MAC_init(context, seed, len, params);
                ASSERT(result == 1);
                return context;
            }

            EVP_MAC_CTX* _ctx;
#else
            EVP_MD_CTX* _ctx;
            EVP_PKEY* _key;
#endif
            Digest _digest = { };
    };
}

namespace Trinity::Crypto
{
    using HMAC_SHA1 = Trinity::Impl::GenericHMAC<EVP_sha1, Constants::SHA1_DIGEST_LENGTH_BYTES>;
    using HMAC_SHA256 = Trinity::Impl::GenericHMAC<EVP_sha256, Constants::SHA256_DIGEST_LENGTH_BYTES>;
}
#endif
