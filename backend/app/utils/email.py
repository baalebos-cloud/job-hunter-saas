# backend/app/utils/email.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.app.core.config import settings


def send_verification_email(to_email: str, token: str):
    """
    Sends an email verification link to a newly registered user via Lark Suite SMTP.
    """
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    subject = "Confirm your email address - Baalebos Cloud"
    
    # HTML Email Template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f9fafb; padding: 40px 20px;">
        <div style="max-w-md; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 12px; border: 1px solid #e5e7eb;">
            <h2 style="color: #4f46e5; margin-top: 0;">Welcome to Baalebos Cloud!</h2>
            <p style="color: #374151; font-size: 16px; line-height: 24px;">
                Thanks for signing up. Please confirm your email address to activate your account and start analyzing your resumes and find your dream jobs.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}" 
                   style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">
                   Verify Email Address
                </a>
            </div>
            <p style="color: #6b7280; font-size: 14px;">
                If the button doesn't work, copy and paste this link into your browser:<br>
                <a href="{verification_link}" style="color: #4f46e5;">{verification_link}</a>
            </p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
            <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">
                If you didn't create an account, you can safely ignore this email.
            </p>
        </div>
    </body>
    </html>
    """

    # Build the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f'{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>'
    msg["To"] = to_email
    
    msg.attach(MIMEText(html_content, "html"))

    try:
        # Connect to Lark Suite via SSL (Port 465)
        with smtplib.SMTP_SSL(settings.SMTP_HOST, int(settings.SMTP_PORT)) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        print(f"[Email] Verification email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send verification email: {str(e)}")
        return False
