#include <cassert>
#include <sstream>
#include <type_traits>

// Keep the production arithmetic/conversion code, substituting only the
// project's fatal assertion backend to avoid linking the whole server.
#define ASSERT(expression, ...) assert(expression)
#include "Cryptography/BigNumber.cpp"

int main()
{
    static_assert(std::is_same_v<decltype(BigNumber().AsByteArray()), std::unique_ptr<uint8[]>>);
    static_assert(std::is_same_v<decltype(BigNumber().AsHexStr()), std::string>);
    static_assert(std::is_same_v<decltype(BigNumber().AsDecStr()), std::string>);

    for (int iteration = 0; iteration < 2000; ++iteration)
    {
        BigNumber number(uint32(0x1234));
        assert(number.AsHexStr() == "1234");
        assert(number.AsDecStr() == "4660");
        auto little = number.AsByteArray(4);
        auto big = number.AsByteArray(4, false);
        uint8 expectedLittle[] = {0x34, 0x12, 0, 0};
        uint8 expectedBig[] = {0, 0, 0x12, 0x34};
        assert(std::memcmp(little.get(), expectedLittle, 4) == 0);
        assert(std::memcmp(big.get(), expectedBig, 4) == 0);
        assert(std::memcmp(number.AsByteArray(0, false).get(), expectedBig + 2, 2) == 0);
        auto moved = std::move(big);
        assert(!big && moved);
        std::ostringstream log;
        log << number.AsHexStr() << ':' << number.AsDecStr();
        assert(log.str() == "1234:4660");

        number.SetDword(uint32(0));
        assert(number.AsHexStr() == "0" && number.AsDecStr() == "0");
        auto zero = number.AsByteArray();
        auto paddedZero = number.AsByteArray(20, false);
        for (int i = 0; i < 20; ++i)
            assert(paddedZero[i] == 0);
        number.SetDword(int32(-1));
        assert(number.AsHexStr() == "-01" && number.AsDecStr() == "-1");
    }
}
