#!/bin/bash
# ---------------------------------------------------------------------------
#  autopatchd - Automated DNF update and reboot configuration tool
# ---------------------------------------------------------------------------
#  Author: Paul Dresch
#  Version: 1.5
#  Date: 2025-10-05
# ---------------------------------------------------------------------------
#  Description:
#    Configures automated package updates on RHEL 9 using dnf-automatic.
#    Provides an interactive CLI (via gum) for SMTP and schedule configuration.
#    Idempotent, logged, and reversible through the --clean option.
# ---------------------------------------------------------------------------

set -euo pipefail
TAG="autopatchd"
CONF="/etc/dnf/automatic.conf"
BACKUP="$CONF.autopatchd.bak"
OVR_DIR="/etc/systemd/system/dnf-automatic-install.timer.d"
OVR_FILE="$OVR_DIR/override.conf"
TIMER="dnf-automatic-install.timer"

# -------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------
log() {
    logger -t "$TAG" "$*"
    echo "[autopatchd] $*"
}

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "This script must be run as root." >&2
        exit 1
    fi
}

# -------------------------------------------------------------
# Ensure gum (Charm CLI) is available
# -------------------------------------------------------------
ensure_gum() {
    if ! command -v gum >/dev/null 2>&1; then
        log "gum not found. Adding Charm repository and installing."
        cat > /etc/yum.repos.d/charm.repo <<'EOF'
[charm]
name=Charm
baseurl=https://repo.charm.sh/yum/
enabled=1
gpgcheck=1
gpgkey=https://repo.charm.sh/yum/gpg.key
EOF
        rpm --import https://repo.charm.sh/yum/gpg.key
        dnf -y install gum
        log "gum installed successfully."
    else
        log "gum already installed."
    fi
}

# -------------------------------------------------------------
# Ensure required dependencies
# -------------------------------------------------------------
ensure_dependencies() {
    log "Ensuring required packages (dnf-automatic)."
    dnf -y install dnf-automatic >/dev/null
    log "Dependencies verified."
}

# -------------------------------------------------------------
# Rollback / clean
# -------------------------------------------------------------
clean_config() {
    log "Initiating autopatchd cleanup."
    systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
    rm -rf "$OVR_DIR"
    if [[ -f "$BACKUP" ]]; then
        mv -f "$BACKUP" "$CONF"
        log "Restored previous configuration from backup."
    fi
    log "Cleanup complete. All changes reverted."
    echo "autopatchd cleanup completed successfully." \
        | gum style --foreground 212
    exit 0
}

# -------------------------------------------------------------
# Write new configuration file
# -------------------------------------------------------------
write_conf() {
    local smtp_host="$1"
    local email_from="$2"
    local email_to="$3"

    if [[ ! -f "$BACKUP" ]]; then
        cp -a "$CONF" "$BACKUP"
        log "Created backup of $CONF"
    fi

    cat > "$CONF" <<EOF
[commands]
upgrade_type = default
random_sleep = 0
download_updates = yes
apply_updates = yes
reboot = when-needed

[emitters]
emit_via = email

[email]
email_from = $email_from
email_to = $email_to
smtp_server = $smtp_host
smtp_port = 587
smtp_auth = none
EOF

    log "Wrote configuration to $CONF"
}

# -------------------------------------------------------------
# Configure systemd override for timer schedule
# -------------------------------------------------------------
setup_timer() {
    local schedule="$1"
    mkdir -p "$OVR_DIR"
    cat > "$OVR_FILE" <<EOF
[Timer]
OnCalendar=
OnCalendar=$schedule
RandomizedDelaySec=300
Persistent=true
EOF
    systemctl daemon-reload
    systemctl enable --now "$TIMER"
    log "Timer $TIMER enabled (OnCalendar=$schedule)"
}

# -------------------------------------------------------------
# Main routine
# -------------------------------------------------------------
main() {
    require_root

    # handle --clean option early
    if [[ "${1:-}" == "--clean" ]]; then
        clean_config
    fi

    ensure_gum
    ensure_dependencies

    # Intro banner
    echo -e "autopatchd configuration tool\n\nThis utility sets up automatic software updates with email reporting." \
        | gum style --border normal --width 60 --padding "1 2" --foreground 212

    # Interactive email and schedule configuration
    local smtp_host email_from email_to default_from default_sched schedule
    default_from="root@$(hostname)"
    smtp_host=$(gum input --placeholder "mail.example.com" --prompt "SMTP relay host (port 465): ")
    [[ -z "$smtp_host" ]] && {
        echo "No SMTP relay provided. Aborting." | gum style --foreground 196
        exit 1
    }

    email_from=$(gum input --placeholder "$default_from" --prompt "Email from address: ")
    email_to=$(gum input --placeholder "$default_from" --prompt "Email to address: ")
    email_from=${email_from:-$default_from}
    email_to=${email_to:-$default_from}

    default_sched="Sun *-*-* 02:00:00"
    schedule=$(gum input --placeholder "$default_sched" --prompt "Systemd OnCalendar time (default: Sunday 02:00): ")
    schedule=${schedule:-$default_sched}

    echo -e "Configuration summary\n\nSMTP relay: $smtp_host\nFrom: $email_from\nTo: $email_to\nSchedule: $schedule" \
        | gum style --border normal --width 65 --padding "1 2" --foreground 250

    if ! gum confirm "Proceed with configuration? "; then
        echo "Setup canceled by user." | gum style --foreground 178
        exit 0
    fi

    gum spin --spinner dot --title "Applying configuration..." -- sleep 3
    write_conf "$smtp_host" "$email_from" "$email_to"
    setup_timer "$schedule"

    # Final summary
    echo -e "autopatchd setup complete\n\n" \
"Automatic updates have been configured.\n" \
"Schedule: $schedule\n" \
"SMTP relay: $smtp_host\n" \
"From: $email_from\n" \
"To: $email_to\n" \
"Backup: $BACKUP\n" \
"Timer: $TIMER (active)\n" \
"Check logs with: journalctl -t autopatchd" \
        | gum style --border normal --width 70 --padding "1 3" --margin "1 2" --foreground 84
}

main "$@"
