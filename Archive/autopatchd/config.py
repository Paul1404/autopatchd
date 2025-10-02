"""
Configuration management for autopatchd
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class EmailConfig:
    smtp_server: str = ""
    smtp_port: int = 587
    from_address: str = ""
    to_addresses: List[str] = field(default_factory=list)
    use_tls: bool = True


@dataclass
class PatchingConfig:
    mode: str = "security"  # security, all, check-only
    reboot: str = "auto"    # auto, never, always
    exclude_packages: List[str] = field(default_factory=list)


@dataclass
class ScheduleConfig:
    timer: str = "Sun 02:00"
    randomize_delay: int = 0  # seconds


@dataclass
class Config:
    email: EmailConfig = field(default_factory=EmailConfig)
    patching: PatchingConfig = field(default_factory=PatchingConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    
    CONFIG_PATH = Path("/etc/autopatchd/config.yaml")
    
    def save(self):
        """Save configuration to file"""
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = {
            "email": {
                "smtp_server": self.email.smtp_server,
                "smtp_port": self.email.smtp_port,
                "from_address": self.email.from_address,
                "to_addresses": self.email.to_addresses,
                "use_tls": self.email.use_tls,
            },
            "patching": {
                "mode": self.patching.mode,
                "reboot": self.patching.reboot,
                "exclude_packages": self.patching.exclude_packages,
            },
            "schedule": {
                "timer": self.schedule.timer,
                "randomize_delay": self.schedule.randomize_delay,
            }
        }
        
        with open(self.CONFIG_PATH, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
    
    @classmethod
    def load(cls) -> 'Config':
        """Load configuration from file"""
        if not cls.CONFIG_PATH.exists():
            raise FileNotFoundError(f"Configuration not found: {cls.CONFIG_PATH}")
        
        with open(cls.CONFIG_PATH, 'r') as f:
            data = yaml.safe_load(f)
        
        config = cls()
        
        if "email" in data:
            email_data = data["email"]
            config.email.smtp_server = email_data.get("smtp_server", "")
            config.email.smtp_port = email_data.get("smtp_port", 587)
            config.email.from_address = email_data.get("from_address", "")
            config.email.to_addresses = email_data.get("to_addresses", [])
            config.email.use_tls = email_data.get("use_tls", True)
        
        if "patching" in data:
            patch_data = data["patching"]
            config.patching.mode = patch_data.get("mode", "security")
            config.patching.reboot = patch_data.get("reboot", "auto")
            config.patching.exclude_packages = patch_data.get("exclude_packages", [])
        
        if "schedule" in data:
            sched_data = data["schedule"]
            config.schedule.timer = sched_data.get("timer", "Sun 02:00")
            config.schedule.randomize_delay = sched_data.get("randomize_delay", 0)
        
        return config