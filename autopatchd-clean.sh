#!/bin/bash
# ---------------------------------------------------------------------------
#  autopatchd-clean.sh - Cleanup utility for autopatchd
# ---------------------------------------------------------------------------
#  Author: Paul Dresch
#  Version: 1.0
#  Date: 2025-10-07
# ---------------------------------------------------------------------------
#  Description:
#    Safely reverts all changes made by autopatchd, restoring system defaults.
#    - Disables and removes systemd timer overrides
#    - Restores original dnf-automatic.conf from backup if present
#    - Cleans gum and charm repo artifacts if desired
#    - Logs all actions via system logger and stdout
# ---------------------------------------------------------------------------

set -euo pipefail
TAG="autopatchd-clean"
CONF="/etc/dnf/automatic.conf"
BACKUP="/etc/dnf/automatic.conf.autopatchd.bak"
OVR_DIR="/etc/systemd/system/dnf-automatic-install.timer.d"
TIMER="dnf-automatic-install.timer"

log() {
    logger -t "$TAG" "$*"
    echo "[autopatchd-clean] $*"
}

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "This script must be run as root." >&2
        exit 1
    fi
}

clean_timer() {
    if systemctl list-timers | grep -q "$TIMER"; then
        log "Disabling and stopping $TIMER"
        systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
    fi

    if [[ -d "$OVR_DIR" ]]; then
        log "Removing override directory: $OVR_DIR"
        rm -rf "$OVR_DIR"
    else
        log "No override files found."
    fi
}

restore_conf() {
    if [[ -f "$BACKUP" ]]; then
        log "Restoring backup configuration from $BACKUP"
        mv -f "$BACKUP" "$CONF"
    else
        log "No $BACKUP found — skipping restore."
    fi
}

clean_gum() {
    read -rp "Do you want to remove gum and its repo (y/N)? " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        log "Removing gum and charm repo"
        rm -f /etc/yum.repos.d/charm.repo
        dnf remove -y gum >/dev/null 2>&1 || true
        log "gum removed."
    else
        log "Keeping gum installed."
    fi
}

finalize() {
    systemctl daemon-reload
    log "Systemd reloaded. Cleanup complete."

    echo -e "\nautopatchd cleanup complete." \
        | gum style --foreground 84 2>/dev/null || echo "autopatchd cleanup complete."
}

main() {
    require_root
    log "Starting autopatchd cleanup sequence..."
    clean_timer
    restore_conf
    clean_gum
    finalize
}

main "$@"
