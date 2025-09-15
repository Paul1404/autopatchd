"""
Utility functions for autopatchd
"""

import logging
import os
import sys
from pathlib import Path


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/var/log/autopatchd/autopatchd.log", mode='a')
        ]
    )
    
    # Ensure log directory exists
    Path("/var/log/autopatchd").mkdir(parents=True, exist_ok=True)


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