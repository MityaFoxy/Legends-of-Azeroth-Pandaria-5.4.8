#!/bin/sh
# Run on the host. Keep the inhibitor alive until the foreground runner exits.
# Do not use podman exec --detach here: it would release the lock immediately.
set -eu

exec systemd-inhibit --what=sleep:idle --mode=block --who=LoA-sanitizer-soak \
    --why='Uninterrupted server sanitizer load test' \
    podman exec --user 0 --workdir /work/Legends-of-Azeroth-Pandaria-5.4.8 \
    loa-build python3 -u contrib/diagnostics/sanitizer_soak.py "$@"
