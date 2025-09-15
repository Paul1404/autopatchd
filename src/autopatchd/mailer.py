import smtplib, ssl, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def _get_password() -> str:
    """Read password injected by systemd-creds into /run/cred/mailpass"""
    try:
        with open("/run/cred/mailpass", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.error("SMTP credential not found. Did you configure systemd unit LoadCredential=?")
        return ""

def send_report(conf, subject, body):
    msg = MIMEMultipart()
    msg["From"] = conf.mail_from
    msg["To"] = conf.mail_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    ctx = ssl.create_default_context()
    password = _get_password()

    if conf.port == 465:
        server = smtplib.SMTP_SSL(conf.relay, conf.port, context=ctx)
    else:
        server = smtplib.SMTP(conf.relay, conf.port)
        server.starttls(context=ctx)

    server.login(conf.username, password)
    server.sendmail(conf.mail_from, [conf.mail_to], msg.as_string())
    server.quit()
    logging.info("Report mailed to %s via %s:%s", conf.mail_to, conf.relay, conf.port)