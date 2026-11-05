#!/bin/sh
# Run on the host. Keep the inhibitor alive until the foreground runner exits.
# Do not use podman exec --detach here: it would release the lock immediately.
set -eu

# Only an active-device override: never save/edit a network profile, reconnect,
# restart NetworkManager or touch an interface that changed connections mid-run.
wifi_device=""
wifi_uuid=""
wifi_power=""
wifi_changed=0
export LC_ALL=C
if command -v nmcli >/dev/null 2>&1; then
    wifi_device=$(nmcli -t -f DEVICE,TYPE,STATE device status | awk -F: '$2 == "wifi" && $3 == "connected" { print $1; exit }')
    if [ -n "$wifi_device" ]; then
        wifi_uuid=$(nmcli -g GENERAL.CON-UUID device show "$wifi_device")
        wifi_power=$(nmcli -g 802-11-wireless.powersave connection show "$wifi_uuid")
        wifi_power=${wifi_power%% *}
        case "$wifi_power" in
            default) wifi_power=0 ;;
            ignore) wifi_power=1 ;;
            disable) wifi_power=2 ;;
            enable) wifi_power=3 ;;
        esac
        if nmcli device modify "$wifi_device" 802-11-wireless.powersave 2; then
            wifi_changed=1
            echo 'Temporary Wi-Fi power saving disabled; connection was not restarted.'
        else
            echo 'WARNING: temporary Wi-Fi power override unavailable; sleep inhibitor still applies.' >&2
        fi
    fi
fi
restore_wifi()
{
    if [ "$wifi_changed" = 1 ] && [ "$(nmcli -g GENERAL.CON-UUID device show "$wifi_device" 2>/dev/null)" = "$wifi_uuid" ]; then
        nmcli device modify "$wifi_device" 802-11-wireless.powersave "$wifi_power" || true
    fi
}
trap restore_wifi EXIT

systemd-inhibit --what=sleep:idle:handle-lid-switch --mode=block --who=LoA-sanitizer-soak \
    --why='Uninterrupted server sanitizer load test' \
    podman exec --user 0 --workdir /work/Legends-of-Azeroth-Pandaria-5.4.8 \
    loa-build python3 -u contrib/diagnostics/sanitizer_soak.py "$@"
