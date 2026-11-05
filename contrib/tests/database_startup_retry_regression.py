#!/usr/bin/env python3
"""Guard bounded startup retries and cleanup of partially opened DB pools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOADER = (ROOT / "src/server/database/Database/DatabaseLoader.cpp").read_text()
POOL = (ROOT / "src/server/database/Database/DatabaseWorkerPool.cpp").read_text()


def block(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


transient = block(LOADER, "bool IsTransientDatabaseError(")
for error in (
        "CR_CONNECTION_ERROR",
        "CR_CONN_HOST_ERROR",
        "CR_SERVER_GONE_ERROR",
        "CR_SERVER_LOST",
        "CR_SERVER_LOST_EXTENDED"):
    assert f"case {error}:" in transient, error

for permanent in ("ER_ACCESS_DENIED_ERROR", "ER_BAD_DB_ERROR", "ER_NO_SUCH_TABLE"):
    assert permanent not in transient, permanent

retry = block(LOADER, "for (uint32 attempt = 1;")
assert "attempt <= _connectionRetryAttempts" in retry
assert "IsTransientDatabaseError(error)" in retry
assert "std::this_thread::sleep_for" in retry
assert "attempt == _connectionRetryAttempts" in retry

assert 'GetIntDefault("Database.ConnectionRetryAttempts", 30)' in LOADER
assert 'GetIntDefault("Database.ConnectionRetryInterval", 1)' in LOADER

open_pool = block(POOL, "uint32 DatabaseWorkerPool<T>::Open()")
for connections in ("_connections[IDX_ASYNC].clear();", "_connections[IDX_SYNCH].clear();"):
    assert open_pool.count(connections) >= 2, connections
assert open_pool.count("_ioContext.reset();") >= 2

for config in (
        "src/server/authserver/authserver.conf.dist",
        "src/server/worldserver/worldserver.conf.dist",
        "src/updater/updater.conf.dist"):
    text = (ROOT / config).read_text()
    assert "Database.ConnectionRetryAttempts = 30" in text, config
    assert "Database.ConnectionRetryInterval = 1" in text, config

print("PASS: transient-only bounded startup retry, failed-pool cleanup, and config defaults")
