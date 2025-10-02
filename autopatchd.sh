#!/bin/sh
# autopatchd - Manage automated patching (dnf-automatic) on RHEL 9
# Author: Paul Dresch

CONFIG_FILE="/etc/dnf/automatic.conf"
BACKUP_FILE="/etc/dnf/automatic.conf.bak"
MSMTP_FILE="/etc/msmtprc"

DRY_RUN=false

log() { printf "%s\n" "$*"; }

run() {
    # Wrapper - if dry-run, just echo the command
    if $DRY_RUN; then
        printf "[dry-run] %s\n" "$*"
    else
        eval "$@"
    fi
}

print_help() {
    cat <<EOF
Usage: autopatchd [OPTIONS]

Options:
  --setup                 Install dnf-automatic (idempotent)
  --install               Enable auto download + install updates
  --download              Enable auto download only
  --notify                Enable notify only
  --default               Use dnf-automatic.timer (config-driven)
  --status                Show active timers
  --disable               Disable all timers
  --smtp                  Configure SMTP interactively
  --dry-run               Show what would be done without applying
  --help                  Show this help

Run without options for interactive menu.
EOF
}

setup() {
    log ">>> Ensuring dnf-automatic is installed..."
    if ! rpm -q dnf-automatic >/dev/null 2>&1; then
        run "dnf -y install dnf-automatic"
    else
        log "Already installed."
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        log ">>> Backing up config to $BACKUP_FILE"
        run "cp $CONFIG_FILE $BACKUP_FILE"
    else
        log "Backup already exists."
    fi
}

enable_timer() {
    timer="$1"
    log ">>> Ensuring timer $timer is enabled..."
    if systemctl is-enabled --quiet "$timer"; then
        log "Already enabled: $timer"
    else
        run "systemctl disable --now 'dnf-automatic'*.timer >/dev/null 2>&1 || true"
        run "systemctl enable --now $timer"
        log "Enabled $timer"
    fi
}

show_status() {
    log ">>> dnf-automatic timers status:"
    if $DRY_RUN; then
        log "[dry-run] systemctl list-timers --all | grep dnf-automatic"
    else
        systemctl list-timers --all | grep dnf-automatic || echo "No active timers."
    fi
}

disable_all() {
    log ">>> Disabling all timers..."
    run "systemctl disable --now 'dnf-automatic'*.timer >/dev/null 2>&1 || true"
}

config_smtp() {
    log ">>> SMTP configuration"
    printf "SMTP Host (e.g. smtp.gmail.com): "
    read -r smtp_host
    printf "SMTP Username: "
    read -r smtp_user
    printf "SMTP Password (app password recommended): "
    stty -echo; read -r smtp_pass; stty echo; echo ""
    printf "From Address: "
    read -r from_addr
    printf "To Address: "
    read -r to_addr

    log ">>> Writing $MSMTP_FILE..."
    if $DRY_RUN; then
        log "[dry-run] Create $MSMTP_FILE with host=$smtp_host, user=$smtp_user, from=$from_addr, to=$to_addr"
    else
        cat > "$MSMTP_FILE" <<EOF
account default
host $smtp_host
port 587
auth on
user $smtp_user
password $smtp_pass
tls on
tls_starttls on
from $from_addr
logfile /var/log/msmtp.log
EOF
        chmod 600 "$MSMTP_FILE"
    fi

    log ">>> Updating $CONFIG_FILE emitter configuration..."
    if $DRY_RUN; then
        log "[dry-run] Update $CONFIG_FILE with command_email + email block"
    else
        awk '
            BEGIN{skip=0}
            /^\[command_email\]/{skip=1}
            /^\[email\]/{skip=0;next}
            skip==1{next}
            {print}
        ' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

        if ! grep -q "command_email" "$CONFIG_FILE"; then
            cat >> "$CONFIG_FILE" <<EOF

[emitters]
emit_via = command_email

[command_email]
command = /usr/bin/msmtp -t

[email]
email_from = $from_addr
email_to = $to_addr
EOF
        fi
    fi
    log ">>> SMTP setup complete."
}

interactive_menu() {
    while true; do
        echo "=== autopatchd interactive mode ==="
        echo "1) Setup dnf-automatic"
        echo "2) Enable auto install mode"
        echo "3) Enable download only"
        echo "4) Enable notify only"
        echo "5) Use default config (dnf-automatic.timer)"
        echo "6) Configure SMTP"
        echo "7) Show status"
        echo "8) Disable all timers"
        echo "9) Exit"
        printf "Choose: "
        read -r choice
        case "$choice" in
            1) setup ;;
            2) enable_timer dnf-automatic-install.timer ;;
            3) enable_timer dnf-automatic-download.timer ;;
            4) enable_timer dnf-automatic-notifyonly.timer ;;
            5) enable_timer dnf-automatic.timer ;;
            6) config_smtp ;;
            7) show_status ;;
            8) disable_all ;;
            9) exit 0 ;;
            *) log "Invalid choice" ;;
        esac
    done
}

# ----------------- MAIN -----------------
ARGS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        *) ARGS="$ARGS $1" ;;
    esac
    shift
done

set -- $ARGS

if [ $# -eq 0 ]; then
    interactive_menu
    exit 0
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --setup) setup ;;
        --install) enable_timer dnf-automatic-install.timer ;;
        --download) enable_timer dnf-automatic-download.timer ;;
        --notify) enable_timer dnf-automatic-notifyonly.timer ;;
        --default) enable_timer dnf-automatic.timer ;;
        --status) show_status ;;
        --disable) disable_all ;;
        --smtp) config_smtp ;;
        --help|-h) print_help; exit 0 ;;
        *) log "Unknown option: $1"; print_help; exit 1 ;;
    esac
    shift
done

log ">>> Done."