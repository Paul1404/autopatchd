import os
import yaml
import subprocess


CONFIG_PATH = "/etc/autopatchd/config.yaml"
CRED_RUNTIME_PATH = "/run/cred/mailpass"
CRED_FILE_PATH = "/etc/autopatchd/smtp-password.cred"


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"No autopatchd config file found at {path}. "
                "Run `autopatchd setup` first."
            )
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        mail_cfg = data.get("mail", {})
        update_cfg = data.get("updates", {})
        log_cfg = data.get("logging", {})

        # Required mail settings
        self.mail_to = mail_cfg.get("to")
        self.mail_from = mail_cfg.get("from")
        self.relay = mail_cfg.get("relay")
        self.port = int(mail_cfg.get("port", 587))
        self.username = mail_cfg.get("username")

        # Other settings
        self.mode = update_cfg.get("mode", "default")
        self.log_dir = log_cfg.get("dir", "/var/log/autopatchd")
        self.schedule = data.get("schedule", "Sun 02:00")

    def get_password(self) -> str:
        """
        Get SMTP password. Normally delivered by systemd-cred injection
        at /run/cred/mailpass. For dev/test outside systemd,
        fall back to 'systemd-creds cat'.
        """
        if os.path.isfile(CRED_RUNTIME_PATH):
            with open(CRED_RUNTIME_PATH, "r") as f:
                return f.read().strip()

        # Debugging fallback
        if os.path.isfile(CRED_FILE_PATH):
            try:
                pw = subprocess.check_output(
                    ["systemd-creds", "cat", "mailpass", "--", CRED_FILE_PATH],
                    text=True
                ).strip()
                return pw
            except subprocess.CalledProcessError:
                raise RuntimeError(
                    "Failed to decrypt credential. "
                    "Run inside systemd unit with LoadCredential."
                )

        raise RuntimeError(
            "No SMTP credential available. "
            "Expected /run/cred/mailpass inside systemd context."
        )