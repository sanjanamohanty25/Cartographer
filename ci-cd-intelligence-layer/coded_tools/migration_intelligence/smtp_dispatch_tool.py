import os
import json
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import request_dir, emails_dir
except ImportError:
    from coded_tools.migration_intelligence._paths import request_dir, emails_dir

logger = logging.getLogger(__name__)

class SmtpDispatchTool(CodedTool):
    """CodedTool that sends the evaluation summary email with PDF and diagram attachments, with mock disk backup."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** SmtpDispatchTool started **********")
        request_id = args.get("request_id")
        recipient_email = args.get("recipient_email")
        subject = args.get("subject", "Cloud Migration Evaluation Report")
        body = args.get("body", "")

        if not request_id or not recipient_email:
            return {"error": "Missing request_id or recipient_email"}

        # Define file paths (dynamic)
        dir_path = request_dir(request_id)
        pdf_path = os.path.join(dir_path, "report.pdf")
        svg_path = os.path.join(dir_path, "diagram.svg")

        # Check files exist
        has_pdf = os.path.exists(pdf_path)
        has_svg = os.path.exists(svg_path)

        # Get SMTP details from environment
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = os.environ.get("SMTP_PORT")
        smtp_user = (os.environ.get("SMTP_USER") or "").strip()
        # ponytail: Gmail App Passwords are shown as 4 space-separated groups but
        # contain no spaces — strip all whitespace so a verbatim paste still logs in.
        smtp_password = "".join((os.environ.get("SMTP_PASSWORD") or "").split())

        email_sent = False
        smtp_error = ""

        # DFD §5 invariant — P6 never dispatches with an attachment missing.
        if not (has_pdf and has_svg):
            missing = [n for n, ok in (("report.pdf", has_pdf), ("diagram.svg", has_svg)) if not ok]
            smtp_error = f"Not dispatched — missing required attachment(s): {missing}"
            logger.error(smtp_error)
        elif smtp_host and smtp_port:
            try:
                logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port}...")
                msg = MIMEMultipart()
                msg['From'] = smtp_user or "noreply@migration-intelligence.local"
                msg['To'] = recipient_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'html'))

                # Attach PDF
                if has_pdf:
                    with open(pdf_path, 'rb') as f:
                        part = MIMEBase('application', 'pdf')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="Report_{request_id}.pdf"')
                        msg.attach(part)

                # Attach SVG diagram
                if has_svg:
                    with open(svg_path, 'rb') as f:
                        part = MIMEBase('image', 'svg+xml')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="Diagram_{request_id}.svg"')
                        msg.attach(part)

                # Send
                server = smtplib.SMTP(smtp_host, int(smtp_port))
                server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(msg['From'], recipient_email, msg.as_string())
                server.quit()
                email_sent = True
                logger.info("Email successfully dispatched via SMTP.")
            except Exception as e:
                smtp_error = str(e)
                logger.error(f"SMTP dispatch failed: {e}")

        # Always write mock output to disk for hackathon/demo verification
        mock_dir = emails_dir()
        mock_path = os.path.join(mock_dir, f"email_{request_id}.json")

        mock_payload = {
            "request_id": request_id,
            "recipient": recipient_email,
            "subject": subject,
            "body": body,
            "attachments": {
                "report_pdf": pdf_path if has_pdf else None,
                "diagram_svg": svg_path if has_svg else None
            },
            "smtp_delivered": email_sent,
            "smtp_error": smtp_error if not email_sent else None
        }

        with open(mock_path, "w", encoding="utf-8") as f:
            json.dump(mock_payload, f, indent=2)

        logger.info(f"Saved email dispatch copy to local file: {mock_path}")
        logger.info("********** SmtpDispatchTool completed **********")

        return {
            "status": "success",
            "smtp_sent": email_sent,
            "mock_path": mock_path
        }
