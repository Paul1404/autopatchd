"""
systemd integration for autopatchd
"""

import subprocess
import os
from pathlib import Path
from jinja2 import Template


class SystemdManager:
    """Manages systemd units and credentials for autopatchd"""
    
    SYSTEMD_DIR = Path("/etc/systemd/system")
    CREDS_DIR = Path("/etc/autopatchd")
    
    def __init__(self, config, smtp_user=None, smtp_pass=None):
        self.config = config
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
    
    def install(self):
        """Install systemd units and credentials"""
        self._create_credentials()
        self._create_service_unit()
        self._create_timer_unit()
        self._create_logrotate_config()
        self._reload_systemd()
        self._enable_timer()
    
    def _create_credentials(self):
        """Create encrypted SMTP credentials"""
        if not self.smtp_pass:
            return
        
        self.CREDS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create credentials file
        creds_content = f"SMTP_USER={self.smtp_user}\nSMTP_PASS={self.smtp_pass}\n"
        
        # Use systemd-creds to encrypt
        cmd = [
            "systemd-creds", "encrypt",
            "--name=autopatchd-smtp",
            "-",
            str(self.CREDS_DIR / "smtp-password.cred")
        ]
        
        try:
            subprocess.run(cmd, input=creds_content.encode(), check=True)
        except subprocess.CalledProcessError:
            # Fallback to plain file if systemd-creds fails
            with open(self.CREDS_DIR / "smtp-password.cred", 'w') as f:
                f.write(creds_content)
            os.chmod(self.CREDS_DIR / "smtp-password.cred", 0o600)
    
    def _create_service_unit(self):
        """Create autopatchd.service unit"""
        service_template = """[Unit]
Description=autopatchd - Automated Patching Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/bin/autopatchd run
StandardOutput=journal
StandardError=journal
LoadCredential=smtp-password.cred:/etc/autopatchd/smtp-password.cred

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.SYSTEMD_DIR / "autopatchd.service"
        with open(service_file, 'w') as f:
            f.write(service_template)
    
    def _create_timer_unit(self):
        """Create autopatchd.timer unit"""
        timer_template = Template("""[Unit]
Description=autopatchd timer - Automated Patching Schedule
Requires=autopatchd.service

[Timer]
OnCalendar={{ schedule }}
Persistent=true
{% if randomize_delay > 0 %}
RandomizedDelaySec={{ randomize_delay }}
{% endif %}

[Install]
WantedBy=timers.target
""")
        
        timer_content = timer_template.render(
            schedule=self.config.schedule.timer,
            randomize_delay=self.config.schedule.randomize_delay
        )
        
        timer_file = self.SYSTEMD_DIR / "autopatchd.timer"
        with open(timer_file, 'w') as f:
            f.write(timer_content)
    
    def _create_logrotate_config(self):
        """Create logrotate configuration"""
        logrotate_content = """/var/log/autopatchd/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        systemctl reload-or-restart rsyslog > /dev/null 2>&1 || true
    endscript
}
"""
        
        logrotate_file = Path("/etc/logrotate.d/autopatchd")
        with open(logrotate_file, 'w') as f:
            f.write(logrotate_content)
    
    def _reload_systemd(self):
        """Reload systemd daemon"""
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    
    def _enable_timer(self):
        """Enable and start the timer"""
        subprocess.run(["systemctl", "enable", "autopatchd.timer"], check=True)
        subprocess.run(["systemctl", "start", "autopatchd.timer"], check=True)
    
    def disable(self):
        """Disable the timer"""
        subprocess.run(["systemctl", "stop", "autopatchd.timer"], 
                      check=False)
        subprocess.run(["systemctl", "disable", "autopatchd.timer"], 
                      check=False)
    
    def cleanup(self):
        """Remove all systemd units and configuration"""
        # Stop and disable
        self.disable()
        
        # Remove units
        units = ["autopatchd.service", "autopatchd.timer"]
        for unit in units:
            unit_file = self.SYSTEMD_DIR / unit
            if unit_file.exists():
                unit_file.unlink()
        
        # Remove configuration
        if self.CREDS_DIR.exists():
            subprocess.run(["rm", "-rf", str(self.CREDS_DIR)], check=False)
        
        # Remove logs
        log_dir = Path("/var/log/autopatchd")
        if log_dir.exists():
            subprocess.run(["rm", "-rf", str(log_dir)], check=False)
        
        # Remove logrotate config
        logrotate_file = Path("/etc/logrotate.d/autopatchd")
        if logrotate_file.exists():
            logrotate_file.unlink()
        
        self._reload_systemd()
    
    def status(self):
        """Show autopatchd status"""
        print("🔍 autopatchd Status")
        print("=" * 40)
        
        # Timer status
        result = subprocess.run(
            ["systemctl", "is-active", "autopatchd.timer"],
            capture_output=True, text=True
        )
        timer_status = result.stdout.strip()
        print(f"Timer: {timer_status}")
        
        # Service status
        result = subprocess.run(
            ["systemctl", "is-active", "autopatchd.service"],
            capture_output=True, text=True
        )
        service_status = result.stdout.strip()
        print(f"Service: {service_status}")
        
        # Next run
        result = subprocess.run(
            ["systemctl", "list-timers", "autopatchd.timer"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("\nNext scheduled run:")
            print(result.stdout)