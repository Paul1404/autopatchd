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
    
    # Check prerequisites
    from .utils import check_dnf_automatic, check_systemd, validate_email, validate_timer_spec
    
    if not check_systemd():
        print("Error: systemd not detected", file=sys.stderr)
        return 1
    
    if not check_dnf_automatic():
        print("Warning: dnf-automatic not found. Install with: dnf install dnf-automatic")
    
    config = Config()
    
    # Email configuration
    print("\n📧 Email Configuration")
    while True:
        smtp_server = input("SMTP server: ").strip()
        if smtp_server:
            config.email.smtp_server = smtp_server
            break
        print("SMTP server is required")
    
    config.email.smtp_port = int(input("SMTP port [587]: ") or "587")
    
    while True:
        from_addr = input("From address: ").strip()
        if from_addr and validate_email(from_addr):
            config.email.from_address = from_addr
            break
        print("Valid email address is required")
    
    while True:
        to_addresses = input("To addresses (comma-separated): ").strip()
        if to_addresses:
            addrs = [addr.strip() for addr in to_addresses.split(",")]
            if all(validate_email(addr) for addr in addrs):
                config.email.to_addresses = addrs
                break
        print("At least one valid email address is required")
    
    smtp_user = input("SMTP username (optional): ").strip() or None
    smtp_pass = None
    if smtp_user:
        import getpass
        smtp_pass = getpass.getpass("SMTP password: ")
    
    # Patching configuration
    print("\n🔄 Patching Configuration")
    modes = ["security", "all", "check-only"]
    print(f"Available modes: {', '.join(modes)}")
    
    while True:
        mode = input("Patching mode [security]: ").strip() or "security"
        if mode in modes:
            config.patching.mode = mode
            break
        print(f"Mode must be one of: {', '.join(modes)}")
    
    reboot_options = ["auto", "never", "always"]
    print(f"Reboot options: {', '.join(reboot_options)}")
    
    while True:
        reboot = input("Reboot policy [auto]: ").strip() or "auto"
        if reboot in reboot_options:
            config.patching.reboot = reboot
            break
        print(f"Reboot policy must be one of: {', '.join(reboot_options)}")
    
    # Schedule configuration
    print("\n⏰ Schedule Configuration")
    print("Examples: 'Sun 02:00', 'daily', 'Mon,Wed,Fri 03:00'")
    
    while True:
        timer = input("Timer schedule [Sun 02:00]: ").strip() or "Sun 02:00"
        if validate_timer_spec(timer):
            config.schedule.timer = timer
            break
        print("Invalid timer specification")
    
    try:
        # Save configuration
        config.save()
        
        # Setup systemd integration
        systemd = SystemdManager(config, smtp_user, smtp_pass)
        systemd.install()
        
        # Create example hooks
        from .hooks import create_example_hooks
        create_example_hooks()
        
        print("\n✅ autopatchd setup complete!")
        print("📁 Configuration: /etc/autopatchd/config.yaml")
        print("🪝 Hook examples: /etc/autopatchd/hooks/")
        print("📊 Logs: /var/log/autopatchd/")
        print("\nNext steps:")
        print("  autopatchd dry-run    # Test configuration")
        print("  autopatchd status     # Check timer status")
        
        return 0
        
    except Exception as e:
        logging.error(f"Setup failed: {e}")
        print(f"Error: Setup failed: {e}", file=sys.stderr)
        return 1
    
def cmd_test_smtp(args):
    """Test SMTP configuration"""
    try:
        config = Config.load()
        from .reporter import test_smtp_connection
        success = test_smtp_connection(config)
        return 0 if success else 1
    except FileNotFoundError:
        print("Error: No configuration found. Run 'autopatchd setup' first.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

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
        
        # Show local results first
        if result.success:
            if result.updates_available:
                print(f"✅ Dry-run complete: {len(result.updates_available)} updates available")
            else:
                print("✅ Dry-run complete: No updates available")
        else:
            print(f"❌ Dry-run failed: {result.error}")
        
        # Then attempt to send email report
        print("\n📧 Sending email report...")
        reporter.send_report(result, dry_run=True)
        
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

def cmd_check_creds(args):
    """Check credential configuration"""
    try:
        config = Config.load()
        
        print("🔐 Credential Check")
        print("=" * 30)
        
        from .reporter import Reporter
        reporter = Reporter(config)
        smtp_user, smtp_pass = reporter._load_smtp_credentials()
        
        if smtp_user and smtp_pass:
            print(f"✅ Credentials found")
            print(f"   User: {smtp_user}")
            print(f"   Password: {'*' * len(smtp_pass)}")
        else:
            print("❌ No credentials found")
            print("\n🔧 To add credentials, run: autopatchd adjust")
        
        # Check credential files
        print("\nCredential File Locations:")
        
        systemd_cred = Path("/run/credentials/autopatchd.service/autopatchd-smtp")
        if systemd_cred.exists():
            print(f"  ✅ systemd runtime: {systemd_cred}")
        else:
            print(f"  ❌ systemd runtime: {systemd_cred} (not found)")
        
        file_cred = Path("/etc/autopatchd/smtp-password.cred")
        if file_cred.exists():
            print(f"  ✅ config file: {file_cred}")
            # Try to determine if it's encrypted or plain
            try:
                with open(file_cred, 'rb') as f:
                    first_bytes = f.read(10)
                if first_bytes.startswith(b'SYSTEMD_CREDENTIAL'):
                    print("    (systemd encrypted)")
                else:
                    print("    (plain text - secure permissions)")
            except:
                pass
        else:
            print(f"  ❌ config file: {file_cred} (not found)")
        
        # Check service unit LoadCredential
        service_file = Path("/etc/systemd/system/autopatchd.service")
        if service_file.exists():
            print(f"\nService Unit: {service_file}")
            try:
                with open(service_file, 'r') as f:
                    content = f.read()
                if "LoadCredential=" in content:
                    for line in content.split('\n'):
                        if "LoadCredential=" in line:
                            print(f"  {line.strip()}")
                else:
                    print("  ❌ No LoadCredential directive found")
            except:
                print("  ❌ Cannot read service file")
        
        return 0
        
    except FileNotFoundError:
        print("Error: No configuration found. Run 'autopatchd setup' first.", file=sys.stderr)
        return 1


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

    # Test SMTP command  
    test_smtp_parser = subparsers.add_parser("test-smtp", help="Test SMTP configuration")
    test_smtp_parser.set_defaults(func=cmd_test_smtp)

    # Check credentials command
    creds_parser = subparsers.add_parser("check-creds", help="Check credential configuration")
    creds_parser.set_defaults(func=cmd_check_creds)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())