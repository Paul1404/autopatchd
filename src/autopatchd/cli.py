import argparse
import os
import subprocess
import sys
import shutil
import tempfile
import getpass
import yaml
from .config import Config
from .runner import run
from .systemd import install_units

# Constants
CONFIG_PATH = "/etc/autopatchd/config.yaml"
CONF_DIR    = "/etc/autopatchd"
CREDS_DIR   = "/etc/autopatchd/creds.conf.d"
CREDS_FILE  = "/etc/autopatchd/smtp-password.cred"
SERVICE     = "/etc/systemd/system/autopatchd.service"
TIMER       = "/etc/systemd/system/autopatchd.timer"
LOGROTATE   = "/etc/logrotate.d/autopatchd"
LOG_DIR     = "/var/log/autopatchd"


def main():
    parser = argparse.ArgumentParser(prog="autopatchd", description="Automated patch daemon")
    subs = parser.add_subparsers(dest="cmd", help="subcommand to run")

    subs.add_parser("run", help="Execute a full patch run (dnf-automatic)")
    subs.add_parser("dry-run", help="Check for updates only, send preview report")
    subs.add_parser("setup", help="Initial interactive setup")
    subs.add_parser("adjust", help="Reconfigure an existing setup")
    subs.add_parser("disable", help="Disable autopatchd.timer but keep configs")
    subs.add_parser("cleanup", help="Disable timer and remove configs + units")

    args = parser.parse_args()

    if args.cmd == "run":
        run(Config(), dry=False)
    elif args.cmd == "dry-run":
        run(Config(), dry=True)
    elif args.cmd in ("setup", "adjust"):
        setup_interactive()
    elif args.cmd == "disable":
        os.system("systemctl disable --now autopatchd.timer")
        print("[INFO] autopatchd timer disabled")
    elif args.cmd == "cleanup":
        cleanup()
    else:
        parser.print_help()


def setup_interactive():
    print("=== autopatchd setup ===")

    mail_to   = input("Mail recipient: ").strip()
    mail_from = input("Mail from (envelope FROM): ").strip()
    relay     = input("SMTP relay hostname: ").strip()
    port      = input("SMTP port [587]: ").strip() or "587"
    user      = input("SMTP username: ").strip()
    pw        = getpass.getpass("SMTP password (hidden): ")
    mode      = input("Update mode (default/security) [default]: ").strip() or "default"
    sched     = input("Schedule (OnCalendar) [Sun 02:00]: ").strip() or "Sun 02:00"

    # Prepare directories
    os.makedirs(CONF_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Store secret securely with systemd-creds
    print("[INFO] Encrypting password with systemd-creds...")
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(pw)
        tmp.flush()
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["systemd-creds", "encrypt", tmp_path, CREDS_FILE],
            check=True
        )
        os.chmod(CREDS_FILE, 0o600)
    except subprocess.CalledProcessError:
        print("[ERROR] systemd-creds encrypt failed. Is systemd >= 250 installed?")
        sys.exit(1)
    finally:
        os.remove(tmp_path)

    # Write config.yaml (no password inside!)
    config = {
        "mail": {
            "to": mail_to,
            "from": mail_from,
            "relay": relay,
            "port": int(port),
            "username": user,
        },
        "updates": {"mode": mode},
        "logging": {"dir": LOG_DIR},
        "schedule": sched,
    }
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    os.chmod(CONFIG_PATH, 0o600)

    # Install systemd units with LoadCredential for password
    install_units(sched)

    print(f"[INFO] autopatchd installed and enabled. Next run scheduled: {sched}")

def cleanup():
    print("[INFO] Cleaning up autopatchd...")
    # stop systemd units
    os.system("systemctl disable --now autopatchd.timer autopatchd.service")

    # remove files
    for path in [SERVICE, TIMER, CONFIG_PATH, LOGROTATE]:
        try:
            os.remove(path)
            print(f"[INFO] removed {path}")
        except FileNotFoundError:
            pass

    for d in [CREDS_DIR, CONF_DIR, LOG_DIR]:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f"[INFO] removed {d}")

    # reload systemd
    os.system("systemctl daemon-reload")
    os.system("systemctl reset-failed autopatchd.service >/dev/null 2>&1")
    print("[INFO] autopatchd cleanup complete.")