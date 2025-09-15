import smtplib, ssl, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_report(conf, subject, body):
    msg = MIMEMultipart()
    msg["From"] = conf.mail_from
    msg["To"] = conf.mail_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    ctx = ssl.create_default_context()
    password = conf.get_password()
    with smtplib.SMTP(conf.relay, conf.port) as s:
        s.starttls(context=ctx)
        s.login(conf.username, password)
        s.sendmail(conf.mail_from, [conf.mail_to], msg.as_string())
    logging.info("Report mailed to %s via %s:%s", conf.mail_to, conf.relay, conf.port)