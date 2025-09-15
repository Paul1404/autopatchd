import yaml, os

class Config:
    def __init__(self, path="/etc/autopatchd/config.yaml"):
        if not os.path.isfile(path):
            raise FileNotFoundError("No autopatchd config found. Run `autopatchd setup`.")
        with open(path) as f:
            data = yaml.safe_load(f)

        self.mail_to = data["mail"]["to"]
        self.mail_from = data["mail"]["from"]
        self.relay = data["mail"]["relay"]
        self.port = data["mail"].get("port", 587)
        self.username = data["mail"]["username"]
        self.cred_file = data["mail"]["cred_file"]

        self.mode = data["updates"]["mode"]
        self.log_dir = data["logging"]["dir"]
        self.schedule = data["schedule"]

    def get_password(self):
        # read systemd-creds decrypted secret (at runtime systemd will supply plaintext)
        with open(self.cred_file, "r") as f:
            return f.read().strip()