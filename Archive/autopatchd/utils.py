"""
Utility functions for autopatchd
"""

import logging
import os
import sys
from pathlib import Path


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    # Ensure log directory exists FIRST
    log_dir = Path("/var/log/autopatchd")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Only add file handler if we can write to the log directory
    log_file = log_dir / "autopatchd.log"
    try:
        handlers.append(logging.FileHandler(str(log_file), mode='a'))
    except (PermissionError, OSError) as e:
        print(f"Warning: Cannot write to log file {log_file}: {e}", file=sys.stderr)
        print("Continuing with console logging only.", file=sys.stderr)
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
        force=True  # Override any existing logging config
    )


def is_root() -> bool:
    """Check if running as root"""
    return os.geteuid() == 0


def check_dnf_automatic():
    """Check if dnf-automatic is available"""
    from shutil import which
    return which("dnf-automatic") is not None


def check_systemd():
    """Check if systemd is available and running"""
    return Path("/run/systemd/system").exists()


def ensure_directory(path: str, mode: int = 0o755):
    """Ensure directory exists with proper permissions"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True, mode=mode)
    return dir_path


def validate_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_timer_spec(timer: str) -> bool:
    """Validate systemd timer specification"""
    # Basic validation for common formats
    valid_patterns = [
        r'^\w+ \d{2}:\d{2}$',  # "Sun 02:00"
        r'^\d{2}:\d{2}$',      # "02:00"
        r'^daily$',             # "daily"
        r'^weekly$',            # "weekly"
        r'^hourly$',            # "hourly"
    ]
    
    import re
    return any(re.match(pattern, timer) for pattern in valid_patterns)