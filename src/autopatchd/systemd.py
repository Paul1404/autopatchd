import os
SERVICE = "/etc/systemd/system/autopatchd.service"

def install_units(schedule):
    svc = f"""[Unit]
Description=autopatchd - OS patch daemon
After=network-online.target

[Service]
Type=oneshot
LoadCredential=mailpass:/etc/autopatchd/smtp-password.cred
ExecStart=/usr/local/bin/autopatchd run
StandardOutput=journal
StandardError=journal
"""
    tmr = f"""[Unit]
Description=autopatchd schedule

[Timer]
OnCalendar={schedule}
Persistent=true

[Install]
WantedBy=timers.target
"""
    open(SERVICE, "w").write(svc)
    open("/etc/systemd/system/autopatchd.timer", "w").write(tmr)
    os.system("systemctl daemon-reload")
    os.system("systemctl enable --now autopatchd.timer")