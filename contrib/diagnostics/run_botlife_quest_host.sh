#!/bin/sh
# Launch via a transient systemd service, not an interactive terminal job.
# The inhibitor lasts only as long as this foreground controller. No network,
# desktop, persistent power configuration or database changes are made here.
set -eu
exec systemd-inhibit --what=sleep:idle --mode=block --who=BotLife-quest-test \
    --why='Autonomous ten-bot quest diagnostics and graceful save' \
    podman exec --user 0 --env PYTHONDONTWRITEBYTECODE=1 \
    --workdir /work/Legends-of-Azeroth-Pandaria-5.4.8 loa-build \
    timeout --signal=TERM --kill-after=300s 9000s nice -n 10 \
    python3 -u contrib/diagnostics/botlife_quest_group_smoke.py "$@"
