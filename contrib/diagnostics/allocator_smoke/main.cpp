#include <cstdlib>
#include <cstring>
#include <new>
#include <thread>
#include <vector>
#ifdef LOA_TEST_MIMALLOC
#include <mimalloc.h>
#endif

int main()
{
    void* memory = std::calloc(16, 32);
    if (!memory)
        return 1;
#ifdef LOA_TEST_MIMALLOC
    if (!mi_check_owned(memory))
        return 2;
#endif
    memory = std::realloc(memory, 4096);
    if (!memory)
        return 3;
    std::memset(memory, 42, 4096);
    // Exercise cross-thread ownership transfer.
    std::thread release([memory] { std::free(memory); });
    release.join();
    auto* aligned = ::operator new(256, std::align_val_t(64));
#ifdef LOA_TEST_MIMALLOC
    if (!mi_check_owned(aligned))
        return 4;
#endif
    ::operator delete(aligned, std::align_val_t(64));
    std::vector<std::thread> workers;
    for (unsigned thread = 0; thread < 4; ++thread)
        workers.emplace_back([] {
            for (unsigned i = 0; i < 10000; ++i)
            {
                std::vector<unsigned> data(1 + i % 1024, i);
                if (data.back() != i)
                    std::abort();
            }
        });
    for (auto& worker : workers)
        worker.join();
}
