# `autopatchd`

`autopatchd` is an automated patch management daemon for RHEL-based systems (RHEL, Rocky Linux, AlmaLinux, CentOS Stream).  
It provides a systemd-managed service and timer that integrates with `dnf-automatic` and delivers update reports via email.  
Configuration is stored under `/etc/autopatchd`, and credentials are secured using `systemd-creds`.

---

## Features

- Automated patching via `dnf-automatic`  
- Configurable for `all` updates or `security`-only  
- Fully systemd-native (`autopatchd.service` + `autopatchd.timer`)  
- Email reporting with SMTP relay support (TLS + authentication)  
- Secrets stored securely using `systemd-creds`  
- Audit-friendly logging:
  - Logs per run under `/var/log/autopatchd/`
  - Journald logging (`journalctl -u autopatchd`)  
  - Log rotation via `/etc/logrotate.d/autopatchd`  
- Lifecycle hooks:
  - Pre-run: `/etc/autopatchd/hooks/pre.d/`
  - Post-run: `/etc/autopatchd/hooks/post.d/`  
- CLI utility `autopatchd` with subcommands for setup, management, and cleanup  
- Dry-run mode for audit/change management preview reports  

---

## Requirements

- Python 3.9+ (works with system Python on RHEL 9/10)  
- `dnf-automatic` package  
- `systemd` with `systemd-creds` (version 250+)  
- Dependencies: `PyYAML`  
- Mail relay reachable with SMTP AUTH (PLAIN/LOGIN over TLS or SSL)

---

## Installation

Clone the repository and install with pip:

```bash
git clone https://github.com/Paul1404/autopatchd.git
cd autopatchd
pip install .
```

This will install the CLI tool `autopatchd`.

---

## Initial Setup

Run the initial interactive setup:

```bash
sudo autopatchd setup
```

The wizard will prompt for:

- Mail recipient  
- Mail sender (envelope MAIL FROM)  
- SMTP relay hostname, port, and credentials  
- Update mode (`default` or `security`)  
- Schedule (systemd `OnCalendar` expression, e.g. `Sun 02:00`)  

During setup:

- A systemd credentials file is created at `/etc/autopatchd/creds.conf.d/smtp-password.cred`  
- `/etc/autopatchd/config.yaml` is written to reference these credentials  
- Systemd unit files are generated:  
  - `/etc/systemd/system/autopatchd.service`  
  - `/etc/systemd/system/autopatchd.timer`  
- The timer is enabled and the service is scheduled  
- A test run is performed and a test mail sent  

---

## Usage

- Run immediately:  
  ```bash
  sudo autopatchd run
  ```
- Preview (dry-run, no packages applied, mail sent):  
  ```bash
  sudo autopatchd dry-run
  ```
- Adjust configuration (rerun setup):  
  ```bash
  sudo autopatchd adjust
  ```
- Disable scheduled runs (keep configs):  
  ```bash
  sudo autopatchd disable
  ```
- Full cleanup (disable, remove configs, units, creds, logs):  
  ```bash
  sudo autopatchd cleanup
  ```

---

## Logs

- Full run reports under `/var/log/autopatchd/report-YYYY-MM-DD_HH-MM-SS.log`  
- Log rotation policy: weekly, 8 rotations, compressed (`/etc/logrotate.d/autopatchd`)  
- Journald logging:  
  ```bash
  journalctl -u autopatchd.service
  ```

---

## Hooks

`autopatchd` can execute arbitrary scripts before and after patch runs:

- Pre-run hooks: `/etc/autopatchd/hooks/pre.d/`
- Post-run hooks: `/etc/autopatchd/hooks/post.d/`

Hooks must be executable and will be invoked in lexical order.  
Each script runs independently; failures are logged but do not abort patching.

Typical uses:
- Notifications to monitoring/Slack  
- Quiescing applications before patching  
- Restarting services after updates  

---

## Security Considerations

- SMTP credentials are not stored in plaintext; handled with `systemd-creds`.  
- `/etc/autopatchd/config.yaml` has mode `0600` to restrict access to root.  
- Logs may contain information about updated packages; control retention with logrotate.  
- Hooks execute as root — only trusted scripts should be placed there.

---

## License

MIT License. See `LICENSE` for details.