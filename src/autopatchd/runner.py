import os, subprocess, logging
from datetime import datetime
from .mailer import send_report
from .hooks import run_hooks

def run(conf, dry=False):
    os.makedirs(conf.log_dir, exist_ok=True)
    ts = datetime.now().strftime("%F_%H-%M-%S")
    logf = os.path.join(conf.log_dir, f"report-{ts}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s autopatchd: %(message)s",
        handlers=[logging.FileHandler(logf), logging.StreamHandler()]
    )

    run_hooks("/etc/autopatchd/hooks/pre.d")
    cmd = ["dnf", "check-update"] if dry else ["/usr/bin/dnf-automatic", "/etc/dnf/automatic.conf", "--timer"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate()
    open(logf, "a").write(out)
    run_hooks("/etc/autopatchd/hooks/post.d")

    subject = f"autopatchd {'DRY-RUN' if dry else 'PATCH'} report - {os.uname().nodename}"
    send_report(conf, subject, out)
    logging.info("Run complete. Log at %s", logf)