"""
Patching functionality - wrapper around dnf-automatic
"""

import subprocess
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from .hooks import HookRunner


@dataclass
class PatchResult:
    """Result of a patching operation"""
    timestamp: datetime
    mode: str
    success: bool
    updates_available: List[str]
    updates_installed: List[str]
    output: str
    error: Optional[str] = None
    reboot_required: bool = False


class Patcher:
    """Handles the actual patching operations"""
    
    LOG_DIR = Path("/var/log/autopatchd")
    
    def __init__(self, config):
        self.config = config
        self.hook_runner = HookRunner()
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    def run(self) -> PatchResult:
        """Run the full patch cycle"""
        logging.info("Starting patch cycle")
        
        result = PatchResult(
            timestamp=datetime.now(),
            mode=self.config.patching.mode,
            success=False,
            updates_available=[],
            updates_installed=[]
        )
        
        try:
            # Run pre-hooks
            logging.info("Running pre-hooks")
            self.hook_runner.run_pre_hooks()
            
            # Check for updates first
            updates = self._check_updates()
            result.updates_available = updates
            
            if not updates:
                logging.info("No updates available")
                result.success = True
                result.output = "No updates available"
            else:
                # Run the actual patching
                if self.config.patching.mode == "check-only":
                    result.output = f"Updates available: {len(updates)} packages"
                    result.success = True
                else:
                    patch_output = self._run_dnf_automatic()
                    result.output = patch_output
                    result.updates_installed = self._parse_installed_packages(patch_output)
                    result.success = True
                    
                    # Check if reboot is needed
                    result.reboot_required = self._check_reboot_required()
                    
                    # Handle reboot policy
                    if result.reboot_required:
                        self._handle_reboot()
            
            # Run post-hooks
            logging.info("Running post-hooks")
            self.hook_runner.run_post_hooks()
            
        except Exception as e:
            logging.error(f"Patch cycle failed: {e}")
            result.error = str(e)
            result.output = f"Error: {e}"
        
        # Write report to log file
        self._write_log_report(result)
        
        return result
    
    def dry_run(self) -> PatchResult:
        """Run a dry-run check only"""
        logging.info("Starting dry-run check")
        
        result = PatchResult(
            timestamp=datetime.now(),
            mode="dry-run",
            success=False,
            updates_available=[],
            updates_installed=[]
        )
        
        try:
            updates = self._check_updates()
            result.updates_available = updates
            result.success = True
            
            if updates:
                result.output = f"Dry-run: {len(updates)} updates available:\n"
                result.output += "\n".join(f"  - {pkg}" for pkg in updates[:10])
                if len(updates) > 10:
                    result.output += f"\n  ... and {len(updates) - 10} more"
            else:
                result.output = "Dry-run: No updates available"
                
        except Exception as e:
            logging.error(f"Dry-run failed: {e}")
            result.error = str(e)
            result.output = f"Dry-run error: {e}"
        
        self._write_log_report(result)
        return result
    
    def _check_updates(self) -> List[str]:
        """Check for available updates"""
        cmd = ["dnf", "check-update", "--quiet"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # dnf check-update returns 100 when updates are available
            if result.returncode == 100:
                # Parse the output to get package names
                packages = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('Last metadata') and '.' in line:
                        # Extract package name (first field)
                        pkg_name = line.split()[0]
                        packages.append(pkg_name)
                return packages
            elif result.returncode == 0:
                return []  # No updates
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to check updates: {e}")
            raise
    
    def _run_dnf_automatic(self) -> str:
        """Run dnf-automatic with appropriate configuration"""
        # Create temporary dnf-automatic config
        config_content = self._generate_dnf_automatic_config()
        config_file = Path("/tmp/autopatchd-dnf-automatic.conf")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        cmd = ["dnf-automatic", "--timer", "--config", str(config_file)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, 
                    f"stdout: {result.stdout}\nstderr: {result.stderr}"
                )
            
            return result.stdout + result.stderr
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("dnf-automatic timed out after 1 hour")
        finally:
            # Clean up temp config
            if config_file.exists():
                config_file.unlink()
    
    def _generate_dnf_automatic_config(self) -> str:
        """Generate dnf-automatic configuration"""
        upgrade_type = "security" if self.config.patching.mode == "security" else "default"
        
        config = f"""[commands]
upgrade_type = {upgrade_type}
random_sleep = 0
network_online_timeout = 60
download_updates = yes
apply_updates = yes

[emitters]
emit_via = stdio

[command_email]
email_from = autopatchd@localhost
email_to = root
email_host = localhost
"""
        return config
    
    def _parse_installed_packages(self, output: str) -> List[str]:
        """Parse installed packages from dnf-automatic output"""
        packages = []
        in_upgrade_section = False
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'Upgrading:' in line or 'Installing:' in line:
                in_upgrade_section = True
                continue
            elif line.startswith('Transaction Summary'):
                in_upgrade_section = False
                continue
            
            if in_upgrade_section and line:
                # Extract package name from upgrade line
                parts = line.split()
                if len(parts) >= 1:
                    packages.append(parts[0])
        
        return packages
    
    def _check_reboot_required(self) -> bool:
        """Check if a reboot is required after patching"""
        # Check for needs-restarting
        try:
            result = subprocess.run(
                ["needs-restarting", "-r"],
                capture_output=True, text=True
            )
            # needs-restarting -r returns 1 if reboot is needed
            return result.returncode == 1
        except FileNotFoundError:
            # needs-restarting not available, check for common indicators
            return self._check_reboot_indicators()
    
    def _check_reboot_indicators(self) -> bool:
        """Check for common reboot indicators"""
        # Check if kernel was updated
        try:
            result = subprocess.run(
                ["rpm", "-q", "--last", "kernel"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # More than one kernel installed
                    return True
        except subprocess.CalledProcessError:
            pass
        
        return False
    
    def _handle_reboot(self):
        """Handle reboot according to policy"""
        policy = self.config.patching.reboot
        
        if policy == "always":
            logging.info("Scheduling immediate reboot")
            subprocess.run(["systemctl", "reboot"], check=False)
        elif policy == "auto":
            logging.info("Scheduling reboot in 5 minutes")
            subprocess.run(["shutdown", "-r", "+5", "autopatchd reboot"], check=False)
        else:  # never
            logging.info("Reboot required but policy is 'never'")
    
    def _write_log_report(self, result: PatchResult):
        """Write detailed report to log file"""
        timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
        log_file = self.LOG_DIR / f"report-{timestamp}.log"
        
        with open(log_file, 'w') as f:
            f.write(f"autopatchd Report - {result.timestamp}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Mode: {result.mode}\n")
            f.write(f"Success: {result.success}\n")
            f.write(f"Updates Available: {len(result.updates_available)}\n")
            f.write(f"Updates Installed: {len(result.updates_installed)}\n")
            f.write(f"Reboot Required: {result.reboot_required}\n\n")
            
            if result.error:
                f.write(f"Error: {result.error}\n\n")
            
            if result.updates_available:
                f.write("Available Updates:\n")
                for pkg in result.updates_available:
                    f.write(f"  - {pkg}\n")
                f.write("\n")
            
            if result.updates_installed:
                f.write("Installed Updates:\n")
                for pkg in result.updates_installed:
                    f.write(f"  - {pkg}\n")
                f.write("\n")
            
            f.write("Full Output:\n")
            f.write("-" * 20 + "\n")
            f.write(result.output)