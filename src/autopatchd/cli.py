#!/usr/bin/env python3
"""
autopatchd CLI - Main command-line interface
"""

import argparse
import sys
import os
import logging
from pathlib import Path

from .config import Config
from .systemd import SystemdManager
from .patcher import Patcher
from .reporter import Reporter
from .utils import setup_logging, is_root


def cmd_setup(args):
    """Interactive setup wizard"""
    if not is_root():
        print("Error: Setup requires root privileges", file=sys.stderr)
        return 1
    
    print("🔧 autopatchd Setup Wizard")
    print("=" * 40)
    
    config = Config()
    
    # Email configuration
    print("\n📧 Email Configuration")
    config.email.smtp_server = input("SMTP server: ")
    config.email.smtp_port = int(input("SMTP port [587]: ") or "587")
    config.email.from_address = input("From address: ")
    
    to_addresses = input("To addresses (comma-separated): ")
    config.email.to_addresses = [addr.strip() for addr in to_addresses.split(",")]
    
    smtp_user = input("SMTP username: ")
    smtp_pass = input("SMTP password: ")
    
    # Patching configuration
    print("\n🔄 Patching Configuration")
    modes = ["security", "all", "check-only"]
    print(f"Available modes: {', '.join(modes)}")
    config.patching.mode = input("Patching mode [security]: ") or "security"
    
    reboot_options = ["auto", "never", "always"]
    print(f"Reboot options: {', '.join(reboot_options)}")
    config.patching.reboot = input("Reboot policy [auto]: ") or "auto"
    
    # Schedule configuration
    print("\n⏰ Schedule Configuration")
    config.schedule.timer = input("Timer schedule [Sun 02:00]: ") or "Sun 02:00"
    
    # Save configuration
    config.save()
    
    # Setup systemd integration
    systemd = SystemdManager(config, smtp_user, smtp_pass)
    systemd.install()
    
    print("\n✅ autopatchd setup complete!")
    print("Use 'autopatchd dry-run' to test configuration")
    return 0


def cmd_run(args):
    """Run patch cycle now"""
    if not is_root():
        print("Error: Run requires root privileges", file=sys.stderr)
        return 1
    
    config = Config.load()
    patcher = Patcher(config)
    reporter = Reporter(config)
    
    try:
        result = patcher.run()
        reporter.send_report(result)
        return 0
    except Exception as e:
        logging.error(f"Patch run failed: {e}")
        return 1


def cmd_dry_run(args):
    """Check updates only, mail preview report"""
    if not is_root():
        print("Error: Dry-run requires root privileges", file=sys.stderr)
        return 1
    
    config = Config.load()
    patcher = Patcher(config)
    reporter = Reporter(config)
    
    try:
        result = patcher.dry_run()
        reporter.send_report(result, dry_run=True)
        print("Dry-run complete. Check your email for the report.")
        return 0
    except Exception as e:
        logging.error(f"Dry-run failed: {e}")
        return 1


def cmd_adjust(args):
    """Rerun setup to change settings"""
    return cmd_setup(args)


def cmd_disable(args):
    """Turn off systemd timer"""
    if not is_root():
        print("Error: Disable requires root privileges", file=sys.stderr)
        return 1
    
    systemd = SystemdManager(None, None, None)
    systemd.disable()
    print("autopatchd disabled")
    return 0


def cmd_cleanup(args):
    """Remove units/configs/logs, disable everything"""
    if not is_root():
        print("Error: Cleanup requires root privileges", file=sys.stderr)
        return 1
    
    print("⚠️  This will remove all autopatchd configuration and logs!")
    confirm = input("Are you sure? [y/N]: ")
    
    if confirm.lower() != 'y':
        print("Cleanup cancelled")
        return 0
    
    systemd = SystemdManager(None, None, None)
    systemd.cleanup()
    print("autopatchd cleaned up")
    return 0


def cmd_status(args):
    """Show autopatchd status"""
    systemd = SystemdManager(None, None, None)
    systemd.status()
    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Enterprise-friendly automated patching daemon",
        prog="autopatchd"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Interactive setup wizard")
    setup_parser.set_defaults(func=cmd_setup)
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run patch cycle now")
    run_parser.set_defaults(func=cmd_run)
    
    # Dry-run command
    dryrun_parser = subparsers.add_parser("dry-run", help="Check updates only")
    dryrun_parser.set_defaults(func=cmd_dry_run)
    
    # Adjust command
    adjust_parser = subparsers.add_parser("adjust", help="Rerun setup")
    adjust_parser.set_defaults(func=cmd_adjust)
    
    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Turn off timer")
    disable_parser.set_defaults(func=cmd_disable)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove everything")
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())