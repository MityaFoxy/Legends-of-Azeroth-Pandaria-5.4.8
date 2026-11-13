#include "AES.h"
#include "ARC4.h"
#include "BigNumber.h"
#include "CryptoHash.h"
#include "HMAC.h"
#include "OpenSSLCrypto.h"
#include "SRP6.h"

#include <algorithm>
#include <array>
#include <iomanip>
#include <iostream>
#include <openssl/crypto.h>
#include <sstream>
#include <string>
#include <utility>

namespace
{
template <typename Container>
std::string ToHex(Container const& data)
{
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (uint8 value : data)
        output << std::setw(2) << unsigned(value);
    return output.str();
}

bool Check(bool condition, char const* name)
{
    if (condition)
        return true;

    std::cerr << "FAIL: " << name << '\n';
    return false;
}
}

int main()
{
    OpenSSLCrypto::threadsSetup({});
    struct OpenSSLCleanup
    {
        ~OpenSSLCleanup() { OpenSSLCrypto::threadsCleanup(); }
    } cleanup;

    bool success = true;
    std::string const message = "The quick brown fox jumps over the lazy dog";
    std::string const key = "key";

    success &= Check(ToHex(Trinity::Crypto::MD5::GetDigestOf(message)) ==
        "9e107d9d372bb6826bd81d3542a419d6", "MD5 known vector");
    success &= Check(ToHex(Trinity::Crypto::SHA1::GetDigestOf(message)) ==
        "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12", "SHA1 known vector");
    success &= Check(ToHex(Trinity::Crypto::SHA256::GetDigestOf(message)) ==
        "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592", "SHA256 known vector");
    success &= Check(ToHex(Trinity::Crypto::HMAC_SHA1::GetDigestOf(key, message)) ==
        "de7c9b85b8b78aa6bc8a7a36f70a90701c9db4d9", "HMAC-SHA1 known vector");
    success &= Check(ToHex(Trinity::Crypto::HMAC_SHA256::GetDigestOf(key, message)) ==
        "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8", "HMAC-SHA256 known vector");

    Trinity::Crypto::HMAC_SHA256 hmacOriginal(key);
    hmacOriginal.UpdateData(message);
    Trinity::Crypto::HMAC_SHA256 hmacCopy(hmacOriginal);
    Trinity::Crypto::HMAC_SHA256 hmacMoved(key);
    hmacMoved = std::move(hmacCopy);
    hmacCopy = hmacOriginal;
    hmacOriginal.Finalize();
    hmacMoved.Finalize();
    hmacCopy.Finalize();
    success &= Check(hmacOriginal.GetDigest() == hmacMoved.GetDigest() &&
        hmacOriginal.GetDigest() == hmacCopy.GetDigest(), "HMAC copy and move state");

    std::array<uint8, 3> const rc4Key = { 'K', 'e', 'y' };
    std::array<uint8, 9> rc4Data = { 'P', 'l', 'a', 'i', 'n', 't', 'e', 'x', 't' };
    std::array<uint8, 9> const expectedRc4 = { 0xBB, 0xF3, 0x16, 0xE8, 0xD9, 0x40, 0xAF, 0x0A, 0xD3 };
    Trinity::Crypto::ARC4 rc4;
    rc4.Init(rc4Key);
    rc4.UpdateData(rc4Data);
    success &= Check(rc4Data == expectedRc4, "RC4 legacy-provider known vector");

    Trinity::Crypto::AES::Key aesKey = {};
    Trinity::Crypto::AES::IV aesIv = {};
    std::array<uint8, 16> aesData = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 };
    std::array<uint8, 16> const originalAesData = aesData;
    Trinity::Crypto::AES::Tag aesTag = {};
    Trinity::Crypto::AES encryptor(true);
    encryptor.Init(aesKey);
    success &= Check(encryptor.Process(aesIv, aesData.data(), aesData.size(), aesTag), "AES-128-GCM encryption");
    Trinity::Crypto::AES decryptor(false);
    decryptor.Init(aesKey);
    success &= Check(decryptor.Process(aesIv, aesData.data(), aesData.size(), aesTag), "AES-128-GCM decryption");
    success &= Check(aesData == originalAesData, "AES-128-GCM round trip");

    BigNumber const base(4);
    BigNumber const exponent(13);
    BigNumber const modulus(497);
    success &= Check(base.ModExp(exponent, modulus).AsDword() == 445, "BigNumber modular exponentiation");

    auto const [salt, verifier] = Trinity::Crypto::SRP6::MakeRegistrationData("USER", "PASSWORD");
    success &= Check(Trinity::Crypto::SRP6::CheckLogin("USER", "PASSWORD", salt, verifier), "SRP6 valid credentials");
    success &= Check(!Trinity::Crypto::SRP6::CheckLogin("USER", "WRONG", salt, verifier), "SRP6 invalid credentials");

    if (!success)
        return 1;

    std::cout << "PASS: project cryptography is compatible with "
              << OpenSSL_version(OPENSSL_VERSION) << '\n';
    return 0;
}
