"""Email service for sending verification emails and notifications."""

import os
import smtplib
import string
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)


def _parse_smtp_port() -> int:
    """
    Parse SMTP_PORT environment variable with error handling.
    
    Returns:
        Port number (default 587 if not set or invalid)
        
    Raises:
        RuntimeError: If SMTP_PORT is set but cannot be parsed
    """
    port_str = os.getenv("SMTP_PORT", "587")
    try:
        return int(port_str)
    except ValueError:
        raise RuntimeError(
            f"Invalid SMTP_PORT value: '{port_str}'. Must be a numeric port number."
        )


def _mask_email(email: str) -> str:
    """
    Mask email address for safe logging.
    
    Examples:
        user@example.com -> u***@example.com
        longname@example.com -> l***@example.com
    """
    if not email or "@" not in email:
        return "[invalid-email]"
    
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 1)
    return f"{masked_local}@{domain}"


class EmailService:
    """Handles email sending for user verification and notifications."""
    
    # Email configuration
    SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT = _parse_smtp_port()
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@consilience.dev")
    APP_NAME = "Consilience"
    APP_URL = os.getenv("APP_URL", "http://localhost:3000")
    
    # Verification token settings
    VERIFICATION_TOKEN_LENGTH = 32
    VERIFICATION_EXPIRY_HOURS = 24
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generate a secure random verification token."""
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(EmailService.VERIFICATION_TOKEN_LENGTH))
        return token
    
    @staticmethod
    def _send_email(
        to_email: str,
        subject: str,
        html_content: str,
        plain_text: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML formatted email body
            plain_text: Plain text fallback (auto-generated if not provided)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Skip in development if SMTP not configured
            if not EmailService.SMTP_USER or EmailService.SMTP_HOST == "localhost":
                masked_recipient = _mask_email(to_email)
                logger.debug(f"[DEV MODE] Email to {masked_recipient}: {subject}")
                return True
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = EmailService.FROM_EMAIL
            message["To"] = to_email
            
            # Add plain text fallback
            if not plain_text:
                plain_text = f"{subject}\n\nPlease view this email in HTML format."
            
            message.attach(MIMEText(plain_text, "plain"))
            message.attach(MIMEText(html_content, "html"))
            
            # Send via SMTP with timeout
            with smtplib.SMTP(
                EmailService.SMTP_HOST,
                EmailService.SMTP_PORT,
                timeout=10
            ) as server:
                server.starttls()
                if EmailService.SMTP_USER:
                    server.login(EmailService.SMTP_USER, EmailService.SMTP_PASSWORD)
                server.send_message(message)
            
            masked_recipient = _mask_email(to_email)
            logger.info(f"Email sent to {masked_recipient}")
            return True
            
        except Exception as e:
            masked_recipient = _mask_email(to_email)
            logger.error(f"Failed to send email to {masked_recipient}: {str(e)}")
            return False
    
    @classmethod
    def send_verification_email(cls, email: str, verification_token: str) -> bool:
        """
        Send email verification link to user.
        
        Args:
            email: User's email address
            verification_token: Token for verification link
            
        Returns:
            True if sent successfully
        """
        # URL-encode the email to handle special characters
        encoded_email = quote(email, safe='')
        verification_url = f"{cls.APP_URL}/verify-email?token={verification_token}&email={encoded_email}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2>Welcome to {cls.APP_NAME}!</h2>
                    <p>Thank you for registering. Please verify your email address to get started.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verification_url}" 
                           style="background-color: #2563eb; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Verify Email Address
                        </a>
                    </div>
                    
                    <p>Or copy this link:</p>
                    <p style="word-break: break-all;"><code>{verification_url}</code></p>
                    
                    <p style="color: #666; font-size: 12px;">
                        This link expires in {cls.VERIFICATION_EXPIRY_HOURS} hours.
                    </p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                    <p style="color: #999; font-size: 12px;">
                        If you didn't create this account, please ignore this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        plain_text = f"""
        Welcome to {cls.APP_NAME}!
        
        Thank you for registering. Please verify your email address:
        {verification_url}
        
        This link expires in {cls.VERIFICATION_EXPIRY_HOURS} hours.
        
        If you didn't create this account, please ignore this email.
        """
        
        return cls._send_email(
            email,
            f"{cls.APP_NAME} - Verify Your Email",
            html_content,
            plain_text
        )
    
    @classmethod
    def send_password_reset_email(cls, email: str, reset_token: str) -> bool:
        """
        Send password reset email to user.
        
        Args:
            email: User's email address
            reset_token: Token for password reset link
            
        Returns:
            True if sent successfully
        """
        reset_url = f"{cls.APP_URL}/reset-password?token={reset_token}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2>Password Reset Request</h2>
                    <p>We received a request to reset your {cls.APP_NAME} password.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" 
                           style="background-color: #2563eb; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    
                    <p>Or copy this link:</p>
                    <p style="word-break: break-all;"><code>{reset_url}</code></p>
                    
                    <p style="color: #666; font-size: 12px;">
                        This link expires in 1 hour.
                    </p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                    <p style="color: #999; font-size: 12px;">
                        If you didn't request this, please ignore this email. Your password will not change.
                    </p>
                </div>
            </body>
        </html>
        """
        
        return cls._send_email(
            email,
            f"{cls.APP_NAME} - Reset Your Password",
            html_content
        )
