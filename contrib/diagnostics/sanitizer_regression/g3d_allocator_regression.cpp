#include "G3D/System.h"
#include <sanitizer/asan_interface.h>
#include <cassert>
#include <cstdint>
#include <cstring>

int main()
{
    // Small allocations must reach ASan individually, rather than being hidden
    // inside a permanently retained G3D slab.
    auto* block = static_cast<unsigned char*>(G3D::System::malloc(16));
    assert(block);
    assert(G3D::System::mallocStatus() == "NO_BUFFERPOOL");
    std::memset(block, 0x5a, 16);
    assert(!__asan_address_is_poisoned(block + 15));
    assert(__asan_address_is_poisoned(block + 16));
    block = static_cast<unsigned char*>(G3D::System::realloc(block, 32));
    assert(block && block[15] == 0x5a);
    assert(__asan_address_is_poisoned(block + 32));
    G3D::System::free(block);
    assert(__asan_address_is_poisoned(block));

    auto* zeros = static_cast<unsigned char*>(G3D::System::calloc(16, 1));
    assert(zeros);
    for (int i = 0; i < 16; ++i)
        assert(zeros[i] == 0);
    G3D::System::free(zeros);

    void* aligned = G3D::System::alignedMalloc(17, 64);
    assert(aligned && reinterpret_cast<std::uintptr_t>(aligned) % 64 == 0);
    G3D::System::alignedFree(aligned);
}
