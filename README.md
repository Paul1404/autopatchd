# autopatchd

Automated patch management daemon for RHEL-based systems (RHEL, Rocky Linux, AlmaLinux, CentOS Stream). Integrates with dnf-automatic to provide scheduled OS updates with email reporting and secure credential management.

## Overview

autopatchd provides a systemd-managed service that automates operating system patching with configurable schedules, security-only or comprehensive updates, and comprehensive email reporting. The system is designed for production environments requiring audit trails, change management integration, and minimal manual intervention.

## Features

### Core Functionality
- Automated patching via dnf-automatic integration
- Flexible update modes: security-only, all updates, or check-only
- Native systemd service and timer configuration
- Intelligent reboot handling with configurable policies
- Pre and post-patching lifecycle hooks

### Reporting and Auditing
- Email notifications with detailed patch reports
- SMTP relay support with TLS authentication
- Per-run log files under `/var/log/autopatchd/`
- Journald integration for centralized logging
- Automatic log rotation with compression
- Dry-run mode for change management previews

### Security
- Credentials secured using systemd-creds (systemd 250+)
- Restrictive file permissions (0600) on configuration
- No plaintext password storage
- Root-only execution model

### Management
- Interactive CLI setup wizard
- Simple adjustment and reconfiguration
- Clean uninstall with full state removal
- Status inspection and validation tools

## Requirements

- Python 3.9 or later
- RHEL-based Linux distribution (RHEL 9+, Rocky Linux 9+, AlmaLinux 9+, CentOS Stream 9+)
- systemd with systemd-creds support (version 250 or later)
- dnf-automatic package
- SMTP relay with authentication support
- Python dependencies: PyYAML, cryptography, jinja2

## Installation

Clone the repository and install using pip:

```bash
git clone https://github.com/Paul1404/autopatchd.git
cd autopatchd
sudo pip install .
```

This installs the `autopatchd` command-line tool system-wide.

## Quick Start

Run the interactive setup wizard:

```bash
sudo autopatchd setup
```

The wizard will prompt for:

1. **Email Configuration**
   - SMTP server hostname and port
   - Sender address (FROM)
   - Recipient addresses (TO)
   - SMTP authentication credentials

2. **Patching Configuration**
   - Update mode: `security`, `all`, or `check-only`
   - Reboot policy: `auto`, `never`, or `always`

3. **Schedule Configuration**
   - Timer specification (systemd OnCalendar format)
   - Examples: `Sun 02:00`, `daily`, `Mon,Wed,Fri 03:00`

The setup process will:
- Create systemd credential files for SMTP authentication
- Generate `/etc/autopatchd/config.yaml`
- Install systemd service and timer units
- Enable and schedule the timer
- Perform a test run and send a test email

## Usage

### Manual Execution

Run patching immediately:
```bash
sudo autopatchd run
```

Preview available updates without applying them:
```bash
sudo autopatchd dry-run
```

### Configuration Management

Modify existing configuration:
```bash
sudo autopatchd adjust
```

Display current status and configuration:
```bash
sudo autopatchd status
```

### Service Control

Disable scheduled patching (keeps configuration):
```bash
sudo autopatchd disable
```

Enable scheduled patching:
```bash
sudo systemctl enable --now autopatchd.timer
```

Check timer status:
```bash
systemctl status autopatchd.timer
```

View service logs:
```bash
journalctl -u autopatchd.service
```

### Complete Removal

Remove all autopatchd configuration, units, credentials, and logs:
```bash
sudo autopatchd cleanup
```

## Configuration

### Configuration File

Primary configuration is stored in `/etc/autopatchd/config.yaml`:

```yaml
email:
  smtp_server: smtp.example.com
  smtp_port: 587
  from_address: autopatchd@example.com
  to_addresses:
    - admin@example.com
  smtp_user: autopatchd@example.com
  smtp_password_cred: smtp-password

patching:
  mode: security  # security, all, or check-only
  reboot: auto    # auto, never, or always

schedule:
  timer: "Sun 02:00"
```

### Credentials

SMTP passwords are stored encrypted using systemd-creds:
- Location: `/etc/autopatchd/creds.conf.d/smtp-password.cred`
- Only accessible by root
- Automatically decrypted by systemd at runtime

### Lifecycle Hooks

Execute custom scripts before and after patching:

**Pre-run hooks:** `/etc/autopatchd/hooks/pre.d/`
- Run before updates are checked or applied
- Use for notifications, service quiescing, or pre-flight checks

**Post-run hooks:** `/etc/autopatchd/hooks/post.d/`
- Run after updates are applied
- Use for service restarts, notifications, or validation

Hooks must be:
- Executable (`chmod +x`)
- Named to control execution order (e.g., `10-notify.sh`, `20-restart.sh`)
- Independent (failures logged but do not halt patching)

Example hook for Slack notification:
```bash
#!/bin/bash
# /etc/autopatchd/hooks/pre.d/10-notify-slack.sh
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"System patching starting"}' \
  https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Logging

### Log Files

Per-run reports are written to:
```
/var/log/autopatchd/report-YYYY-MM-DD_HH-MM-SS.log
```

Each report contains:
- Timestamp and execution mode
- Available updates list
- Installed packages
- Reboot requirement status
- Success or failure indication
- Error details if applicable

### Log Rotation

Automatic rotation via `/etc/logrotate.d/autopatchd`:
- Weekly rotation schedule
- 8 rotations retained
- Compressed with gzip
- Does not interfere with running processes

### Journald Integration

View service logs:
```bash
# Recent logs
journalctl -u autopatchd.service

# Follow in real-time
journalctl -u autopatchd.service -f

# Logs since last boot
journalctl -u autopatchd.service -b

# Logs for specific date range
journalctl -u autopatchd.service --since "2026-01-01" --until "2026-01-14"
```

## Shell Scripts

The repository includes standalone shell scripts for legacy or minimal installations:

- **autopatchd.sh**: Original dnf-automatic configuration tool with gum-based interactive interface
- **autopatchd-mail.sh**: Postfix relay configuration utility
- **autopatchd-status.sh**: System inspection and status reporting
- **autopatchd-clean.sh**: Cleanup and uninstallation script

These scripts are maintained for compatibility but the Python-based CLI tool is recommended for new deployments.

## Update Modes

### Security Mode
```bash
sudo autopatchd setup  # Select "security" mode
```
- Applies only security-related updates
- Minimal change surface
- Recommended for production systems

### All Updates Mode
```bash
sudo autopatchd setup  # Select "all" mode
```
- Applies all available updates
- Includes bugfixes and enhancements
- Use in development or test environments

### Check-Only Mode
```bash
sudo autopatchd setup  # Select "check-only" mode
```
- Reports available updates without applying
- Generates email notifications
- Useful for change management workflows

## Reboot Policies

### Auto (Recommended)
- Reboots only when kernel, systemd, or glibc are updated
- Minimizes downtime while ensuring critical updates are applied

### Never
- Never automatically reboots
- Updates requiring reboot remain pending
- Administrator must manually reboot

### Always
- Reboots after every successful patch run
- Ensures all updates are fully applied
- Suitable for development systems

## Security Considerations

### Credential Management
- SMTP passwords never stored in plaintext
- systemd-creds provides encryption at rest
- Credentials only accessible to root user
- Automatic decryption by systemd at runtime

### File Permissions
- Configuration files: 0600 (root read/write only)
- Log directory: 0755 (root write, all read)
- Hook directories: 0700 (root only)

### Execution Context
- All operations run as root via sudo
- Hooks execute with root privileges
- Only install trusted scripts in hook directories

### Audit Trail
- All patch operations logged to files and journal
- Email notifications provide external audit record
- Log retention controlled by logrotate policy

## Troubleshooting

### Setup Fails with "systemd-creds not found"
Ensure systemd version 250 or later is installed:
```bash
systemctl --version
```

### No Email Received After Test Run
Check SMTP configuration and logs:
```bash
journalctl -u autopatchd.service | grep -i smtp
tail -f /var/log/autopatchd/report-*.log
```

Verify network connectivity to SMTP server:
```bash
nc -zv smtp.example.com 587
```

### Service Fails to Start
Check service status and logs:
```bash
systemctl status autopatchd.service
journalctl -u autopatchd.service -n 50
```

Verify configuration file syntax:
```bash
python3 -c "import yaml; yaml.safe_load(open('/etc/autopatchd/config.yaml'))"
```

### Updates Not Being Applied
Verify dnf-automatic is installed:
```bash
rpm -q dnf-automatic
```

Check patching mode in configuration:
```bash
grep mode /etc/autopatchd/config.yaml
```

### Timer Not Running
Check timer status:
```bash
systemctl status autopatchd.timer
systemctl list-timers autopatchd.timer
```

Enable if necessary:
```bash
sudo systemctl enable --now autopatchd.timer
```

## Contributing

Contributions are welcome. Please ensure:
- Code follows existing style conventions
- New features include appropriate documentation
- Security-sensitive changes are reviewed carefully
- Testing on multiple RHEL-based distributions

## License

MIT License

Copyright (c) 2025 Paul Dresch

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Author

Paul Dresch

## Links

- Repository: https://github.com/Paul1404/autopatchd
- Issues: https://github.com/Paul1404/autopatchd/issues
