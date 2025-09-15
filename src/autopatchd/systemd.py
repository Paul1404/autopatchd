import subprocess, os

SERVICE = "/etc/systemd/system/autopatchd.service"
TIMER = "/etc/systemd/system/autopatchd.timer"

def install_units(schedule):
    open(SERVICE, "w").write(f"""[Unit]
Description=autopatchd - automatic system patch daemon
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/autopatchd run
StandardOutput=journal
StandardError=journal
""")

    open(TIMER, "w").write(f"""[Unit]
Description=autopatchd schedule
[Timer]
OnCalendar={schedule}
Persistent=true

[Install]
WantedBy=timers.target
""")
    subprocess.run(["systemctl","daemon-reload"])
    subprocess.run(["systemctl","enable","--now","autopatchd.timer"])