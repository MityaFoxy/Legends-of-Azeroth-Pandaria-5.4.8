#!/usr/bin/env python3
"""Stress ConditionMgr vehicle-AI registration from concurrent map threads."""

import os
import pathlib
import subprocess
import sys
import tempfile


root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def method(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


header = (root / "src/server/game/Conditions/ConditionMgr.h").read_text()
register_method = method(
    header, "void RegisterVehicleAI(VehicleAIBase* ai)"
)
unregister_method = method(
    header, "void UnregisterVehicleAI(VehicleAIBase* ai)"
)

source = (
    r"""
#include <array>
#include <atomic>
#include <cassert>
#include <cstddef>
#include <mutex>
#include <thread>
#include <unordered_set>
#include <vector>

class VehicleAIBase { };

class ConditionMgr
{
public:
"""
    + register_method
    + "\n"
    + unregister_method
    + r"""

    bool Empty()
    {
        std::lock_guard<std::mutex> lock(m_vehicleAIsLock);
        return m_vehicleAIs.empty();
    }

private:
    std::mutex m_vehicleAIsLock;
    std::unordered_set<VehicleAIBase*> m_vehicleAIs;
};

int main()
{
    constexpr std::size_t ThreadCount = 8;
    constexpr std::size_t VehiclesPerThread = 32;
    constexpr std::size_t Iterations = 20000;

    ConditionMgr manager;
    std::array<VehicleAIBase, ThreadCount * VehiclesPerThread> vehicles;
    std::atomic<bool> start = false;
    std::vector<std::thread> workers;

    for (std::size_t thread = 0; thread < ThreadCount; ++thread)
    {
        workers.emplace_back([&, thread]
        {
            while (!start.load(std::memory_order_acquire))
                std::this_thread::yield();

            std::size_t const first = thread * VehiclesPerThread;
            for (std::size_t iteration = 0; iteration < Iterations; ++iteration)
            {
                VehicleAIBase* vehicle = &vehicles[first + iteration % VehiclesPerThread];
                manager.RegisterVehicleAI(vehicle);
                manager.UnregisterVehicleAI(vehicle);
            }
        });
    }

    start.store(true, std::memory_order_release);
    for (std::thread& worker : workers)
        worker.join();

    assert(manager.Empty());
}
"""
)

with tempfile.TemporaryDirectory(prefix="loa-vehicle-condition-regression-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run(
        [
            compiler,
            "-x",
            "c++",
            "-std=c++20",
            "-g",
            "-O1",
            "-fsanitize=thread",
            "-fno-omit-frame-pointer",
            "-pthread",
            "-",
            "-o",
            str(binary),
        ],
        input=source,
        text=True,
        check=True,
    )
    environment = os.environ.copy()
    environment["TSAN_OPTIONS"] = "halt_on_error=1"
    subprocess.run([str(binary)], env=environment, check=True)

assert "std::mutex m_vehicleAIsLock" in header
print("Concurrent vehicle condition registry regression: PASS")
