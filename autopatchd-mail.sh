#!/bin/bash
# ---------------------------------------------------------------------------
#  autopatchd-mail - Postfix relay configuration for autopatchd
# ---------------------------------------------------------------------------
#  Author: Paul (Systems Engineer, Linux)
#  Version: 1.3
#  Date: 2025-10-05
# ---------------------------------------------------------------------------

set -euo pipefail
TAG="autopatchd-mail"

log() { logger -t "$TAG" "$*"; echo "[autopatchd-mail] $*"; }

require_root() { [[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }; }

detect_map_type() {
    if postconf -m | grep -qw lmdb; then echo "lmdb"; else echo "hash"; fi
}

ensure_postfix() {
    if ! rpm -q postfix >/dev/null 2>&1; then
        dnf -y install postfix
        systemctl enable --now postfix
        log "Postfix installed and started."
    else
        systemctl enable --now postfix
        log "Postfix already installed and running."
    fi
}

clean_config() {
    log "Cleaning Postfix relay configuration."
    rm -f /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.{db,lmdb}
    rm -f /etc/postfix/canonical /etc/postfix/canonical.{db,lmdb}
    sed -i '/^relayhost =/d;
            /^smtp_sasl_/d;
            /^smtp_use_tls/d;
            /^smtp_tls_security_level/d;
            /^smtp_tls_wrappermode/d;
            /^canonical_maps/d;
            /^sender_canonical_maps/d' /etc/postfix/main.cf
    systemctl restart postfix
    log "Postfix relay configuration removed."
    echo "autopatchd-mail cleanup complete."
    exit 0
}

send_test_mail() {
    local target="$1"
    echo "Test message from $(hostname) via autopatchd-mail" \
        | mail -s "autopatchd-mail test from $(hostname)" "$target"
    echo "Test message sent to $target. Check recipient mailbox." \
        | gum style --foreground 84
    exit 0
}

configure_postfix() {
    local relay port relay_user relay_pass rewrite_from display_name maptype
    maptype=$(detect_map_type)
    log "Detected supported map type: $maptype"

    echo -e "autopatchd-mail Postfix relay setup\n\nThis will configure Postfix to relay outbound mail via an external SMTP relay." \
        | gum style --border normal --width 70 --padding "1 2" --foreground 212

    relay=$(gum input --placeholder "mail.example.com" --prompt "SMTP relay hostname: ")
    [[ -z "$relay" ]] && { echo "Relay required. Aborting." | gum style --foreground 196; exit 1; }

    port=$(gum input --placeholder "465" --prompt "SMTP relay port (465 or 587): ")
    port=${port:-465}

    relay_user=$(gum input --placeholder "user@example.com" --prompt "SMTP relay username (leave blank if none): ")
    relay_pass=$(gum input --password --prompt "SMTP relay password (leave blank if none): ")
    rewrite_from=$(gum input --placeholder "autopatch@pdcd.net" --prompt "Rewrite outgoing mail as (From address): ")
    display_name=$(gum input --placeholder "Autopatch Daemon" --prompt "Sender display name (optional): ")

    log "Configuring Postfix for relayhost=$relay:$port, user=$relay_user, from=$rewrite_from, name=$display_name"

    ensure_postfix
    postconf -e "relayhost = [$relay]:$port"

    # TLS wrapper detection
    if [[ "$port" == "465" ]]; then
        postconf -e "smtp_tls_wrappermode = yes"
        postconf -e "smtp_tls_security_level = encrypt"
        postconf -e "smtp_use_tls = no"
        log "Configured SMTPS wrapper mode for port 465."
    else
        postconf -e "smtp_tls_wrappermode = no"
        postconf -e "smtp_tls_security_level = encrypt"
        postconf -e "smtp_use_tls = yes"
        log "Configured STARTTLS mode for port $port."
    fi

    if [[ -n "$relay_user" && -n "$relay_pass" ]]; then
        echo "[$relay]:$port    $relay_user:$relay_pass" > /etc/postfix/sasl_passwd
        postconf -e "smtp_sasl_auth_enable = yes"
        postconf -e "smtp_sasl_password_maps = $maptype:/etc/postfix/sasl_passwd"
        postconf -e "smtp_sasl_security_options = noanonymous"
        postconf -e "smtp_sasl_tls_security_options = noanonymous"
        if ! postmap "$maptype:/etc/postfix/sasl_passwd"; then
            log "LMDB map creation failed; reverting to hash."
            maptype="hash"
            postmap hash:/etc/postfix/sasl_passwd
            postconf -e "smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd"
        fi
        chmod 600 /etc/postfix/sasl_passwd*
    else
        postconf -e "smtp_sasl_auth_enable = no"
        rm -f /etc/postfix/sasl_passwd*
    fi

    # Canonical map with sanitized key<tab>value format
    local canonical_line
    if [[ -n "$display_name" ]]; then
        canonical_line="root@$(hostname)\t${display_name} <${rewrite_from}>"
    else
        canonical_line="root@$(hostname)\t${rewrite_from}"
    fi
    printf "%b\n" "$canonical_line" > /etc/postfix/canonical

    postconf -e "canonical_maps = $maptype:/etc/postfix/canonical"
    postconf -e "sender_canonical_maps = $maptype:/etc/postfix/canonical"

    if ! postmap "$maptype:/etc/postfix/canonical"; then
        log "LMDB map creation failed; reverting to hash."
        maptype="hash"
        postmap hash:/etc/postfix/canonical
        postconf -e "canonical_maps = hash:/etc/postfix/canonical"
        postconf -e "sender_canonical_maps = hash:/etc/postfix/canonical"
    fi

    systemctl restart postfix
    log "Postfix configured and restarted."
    echo -e "Postfix relay configuration complete\n\nRelay: $relay\nPort:  $port\nUser:  $relay_user\nFrom:  $rewrite_from\nName:  $display_name\nMap type:  $maptype" \
        | gum style --border normal --width 70 --padding "1 3" --margin "1 2" --foreground 84
}

main() {
    require_root
    case "${1:-}" in
        --clean)
            clean_config
            ;;
        --test)
            shift
            [[ -z "${1:-}" ]] && { echo "Usage: $0 --test <address>"; exit 1; }
            send_test_mail "$1"
            ;;
        *)
            if ! command -v gum >/dev/null 2>&1; then
                dnf -y install gum
            fi
            configure_postfix
            ;;
    esac
}

main "$@"
