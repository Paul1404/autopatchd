#!/bin/bash
# ---------------------------------------------------------------------------
#  autopatchd-status - Inspection tool for autopatchd and mail relay config
# ---------------------------------------------------------------------------
#  Author: Paul (Systems Engineer, Linux)
#  Version: 1.0
#  Date: 2025-10-05
# ---------------------------------------------------------------------------
#  Description:
#    Summarises configuration and health of autopatchd (dnf-automatic)
#    and the outbound mail relay environment.
# ---------------------------------------------------------------------------

set -euo pipefail
TAG="autopatchd-status"

log() { echo "[autopatchd-status] $*"; }

sep() { printf "\n\033[1;34m---- %s ----\033[0m\n" "$1"; }

require_root() {
    [[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }
}

# -------------------------------------------------------------
# Collect DNF Automatic information
# -------------------------------------------------------------
show_dnf_automatic() {
    sep "DNF Automatic Configuration"
    if [[ -f /etc/dnf/automatic.conf ]]; then
        grep -E '^(download_updates|apply_updates|reboot|email_|smtp_)' \
            /etc/dnf/automatic.conf || true
    else
        echo "Configuration file not found."
    fi

    sep "Timer Status"
    if systemctl list-timers --all | grep -q dnf-automatic-install.timer; then
        systemctl status dnf-automatic-install.timer --no-pager | awk '/Loaded|Active|Trigger/ {print}'
    else
        echo "dnf-automatic-install.timer not found."
    fi
}

# -------------------------------------------------------------
# Collect Postfix / relay information
# -------------------------------------------------------------
show_postfix() {
    if ! systemctl is-active --quiet postfix; then
        log "Postfix is not active."
        return
    fi

    sep "Postfix Relay Parameters"
    postconf -n | grep -E '^(relayhost|smtp_tls_|smtp_use_tls|smtp_sasl_|canonical_)' || true

    sep "Canonical Map"
    if [[ -f /etc/postfix/canonical ]]; then
        cat /etc/postfix/canonical
    else
        echo "No canonical map configured."
    fi

    sep "SASL Credentials"
    if [[ -f /etc/postfix/sasl_passwd ]]; then
        grep -v '.*password.*' /etc/postfix/sasl_passwd
        ls -l /etc/postfix/sasl_passwd*
    else
        echo "No SASL credentials file found."
    fi
}

# -------------------------------------------------------------
# Dry-run mail test
# -------------------------------------------------------------
test_mail() {
    local target="$1"
    local tmp="/tmp/autopatchd-testmail.txt"
    echo "autopatchd mail test from $(hostname) on $(date)" > "$tmp"
    mail -s "autopatchd test mail from $(hostname)" "$target" < "$tmp"
    rm -f "$tmp"
    echo "Test mail queued to $target (check /var/log/maillog)."
}

# -------------------------------------------------------------
# Entry
# -------------------------------------------------------------
main() {
    require_root

    case "${1:-}" in
        --test-mail)
            shift
            [[ -z "${1:-}" ]] && { echo "Usage: $0 --test-mail <recipient>"; exit 1; }
            test_mail "$1"
            ;;
        *)
            log "autopatchd system status for $(hostname)"
            show_dnf_automatic
            show_postfix
            ;;
    esac
}

main "$@"
