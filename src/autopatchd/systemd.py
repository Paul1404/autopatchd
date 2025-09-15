"""
systemd integration for autopatchd
"""

import subprocess
import os
from pathlib import Path
from jinja2 import Template
import logging


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
        if not self.smtp_user or not self.smtp_pass:
            logging.info("No SMTP credentials provided, skipping credential creation")
            return
        
        self.CREDS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create credentials content
        creds_content = f"SMTP_USER={self.smtp_user}\nSMTP_PASS={self.smtp_pass}\n"
        creds_file = self.CREDS_DIR / "smtp-password.cred"
        
        # Try systemd-creds first
        try:
            logging.info("Attempting to create encrypted credentials with systemd-creds")
            
            # First create a temporary plain file
            temp_plain = self.CREDS_DIR / "smtp-password.plain"
            with open(temp_plain, 'w') as f:
                f.write(creds_content)
            os.chmod(temp_plain, 0o600)
            
            # Use systemd-creds encrypt with correct syntax
            cmd = [
                "systemd-creds", "encrypt",
                "--name=autopatchd-smtp",
                str(temp_plain),
                str(creds_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Remove the temporary plain file
            temp_plain.unlink()
            
            logging.info("✅ Credentials encrypted with systemd-creds")
            logging.debug(f"systemd-creds output: {result.stdout}")
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.warning(f"systemd-creds failed or not available: {e}")
            logging.info("Falling back to plain text credential file")
            
            # Clean up temp file if it exists
            temp_plain = self.CREDS_DIR / "smtp-password.plain"
            if temp_plain.exists():
                temp_plain.unlink()
            
            # Fallback to plain file
            with open(creds_file, 'w') as f:
                f.write(creds_content)
            os.chmod(creds_file, 0o600)
            logging.info("✅ Credentials stored in plain text file (secure permissions)")
        
        # Verify the file was created
        if creds_file.exists():
            logging.info(f"Credentials file created: {creds_file}")
        else:
            logging.error("Failed to create credentials file")
    
    def _create_service_unit(self):
        """Create autopatchd.service unit"""
        # Check if we should load credentials
        creds_line = ""
        creds_file = self.CREDS_DIR / "smtp-password.cred"
        if creds_file.exists():
            # Use the correct LoadCredential syntax: name:path
            creds_line = f"LoadCredential=autopatchd-smtp:{creds_file}"
        
        service_template = f"""[Unit]
Description=autopatchd - Automated Patching Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/bin/autopatchd run
StandardOutput=journal
StandardError=journal
{creds_line}

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.SYSTEMD_DIR / "autopatchd.service"
        with open(service_file, 'w') as f:
            f.write(service_template)
        logging.info(f"Service unit created: {service_file}")
    
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
        logging.info(f"Timer unit created: {timer_file}")
    
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
        logging.info(f"Logrotate config created: {logrotate_file}")
    
    def _reload_systemd(self):
        """Reload systemd daemon"""
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        logging.info("systemd daemon reloaded")
    
    def _enable_timer(self):
        """Enable and start the timer"""
        subprocess.run(["systemctl", "enable", "autopatchd.timer"], check=True)
        subprocess.run(["systemctl", "start", "autopatchd.timer"], check=True)
        logging.info("Timer enabled and started")
    
    def disable(self):
        """Disable the timer"""
        subprocess.run(["systemctl", "stop", "autopatchd.timer"], check=False)
        subprocess.run(["systemctl", "disable", "autopatchd.timer"], check=False)
        logging.info("Timer disabled")
    
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
                logging.info(f"Removed unit: {unit_file}")
        
        # Remove configuration
        if self.CREDS_DIR.exists():
            subprocess.run(["rm", "-rf", str(self.CREDS_DIR)], check=False)
            logging.info(f"Removed config directory: {self.CREDS_DIR}")
        
        # Remove logs
        log_dir = Path("/var/log/autopatchd")
        if log_dir.exists():
            subprocess.run(["rm", "-rf", str(log_dir)], check=False)
            logging.info(f"Removed log directory: {log_dir}")
        
        # Remove logrotate config
        logrotate_file = Path("/etc/logrotate.d/autopatchd")
        if logrotate_file.exists():
            logrotate_file.unlink()
            logging.info(f"Removed logrotate config: {logrotate_file}")
        
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
        
        # Check credentials
        creds_file = self.CREDS_DIR / "smtp-password.cred"
        if creds_file.exists():
            print(f"Credentials: Found ({creds_file})")
        else:
            print("Credentials: Not found")
        
        # Next run
        result = subprocess.run(
            ["systemctl", "list-timers", "autopatchd.timer"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("\nNext scheduled run:")
            print(result.stdout)