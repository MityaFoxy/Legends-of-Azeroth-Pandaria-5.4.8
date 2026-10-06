#include "Unaligned.h"
#include "BitMask.h"
#include "FlaggedValues.h"
#include "DetourNavMesh.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>

template <typename T>
void CheckUnaligned(T value)
{
    alignas(8) std::array<char, sizeof(T) + 8> bytes{};
    for (unsigned offset = 1; offset < 8; ++offset)
    {
        WriteUnaligned(bytes.data() + offset, value);
        assert(ReadUnaligned<T>(bytes.data() + offset) == value);
        assert(std::memcmp(bytes.data() + offset, &value, sizeof(value)) == 0);
    }
}

int main()
{
    CheckUnaligned<std::uint16_t>(0xF123);
    CheckUnaligned<std::int32_t>(-1234567);
    CheckUnaligned<std::uint64_t>(0xFEDCBA9876543210ULL);
    CheckUnaligned<float>(-3.5f);
    CheckUnaligned<double>(1.25);
    int local = 0;
    CheckUnaligned(&local);
    assert(MakeOneBasedMask32(0) == 0);
    assert(MakeOneBasedMask32(1) == 1);
    assert(MakeOneBasedMask32(32) == 0x80000000U);
    assert(MakeOneBasedMask32(33) == 0);
    assert(MakeOneBasedMask32(std::uint32_t(-1)) == 0);

    FlaggedValuesArray32<int, std::uint64_t, unsigned, 38> visibility;
    for (unsigned bit = 0; bit < 38; ++bit)
    {
        visibility.AddFlag(bit);
        assert(visibility.HasFlag(bit));
        assert(visibility.GetFlags() == (std::uint64_t(1) << (bit + 1)) - 1);
    }
    visibility.DelFlag(36);
    assert(!visibility.HasFlag(36));
    assert(visibility.HasFlag(4)); // previously bit 36 collided with bit 4
    visibility.AddFlag(38); // invalid input must not trigger an invalid shift
    FlaggedValuesArray32<int, std::uint32_t, unsigned, 32> flags;
    flags.AddFlag(31);
    assert(flags.GetFlags() == 0x80000000U);

    static_assert(sizeof(dtLink) == 16);
    static_assert(alignof(dtLink) == 4);
    alignas(8) char links[sizeof(dtLink) + 4]{};
    auto* link = new (links + 4) dtLink{};
    link->ref = 0xFEDCBA9876543210ULL;
    link->next = 7;
    assert(link->ref == 0xFEDCBA9876543210ULL && link->next == 7);
}
