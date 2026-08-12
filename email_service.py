import os
import random
import requests


def generate_reset_code() -> str:
    """Generate a 6-digit numeric reset code."""
    return f"{random.randint(100000, 999999)}"


def _build_email_bodies(code: str, user_name: str | None = None) -> tuple[str, str]:
    greeting = f"Hi {user_name}," if user_name else "Hi,"
    html_body = f"""
    <html>
    <body style="font-family: 'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif; color: #1e293b; background: #f8fafc; padding: 40px 20px;">
      <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 20px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.06);">
        <div style="text-align: center; margin-bottom: 32px;">
          <h1 style="font-size: 24px; font-weight: 800; color: #0f172a; margin: 0;">Pivot</h1>
          <p style="font-size: 13px; color: #64748b; margin: 4px 0 0;">Athlete Resilience Platform</p>
        </div>
        <p style="font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="font-size: 15px; line-height: 1.6; color: #334155;">
          We received a request to reset your Pivot password. Use the code below to verify your identity:
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <div style="display: inline-block; background: linear-gradient(135deg, #3b82f6, #2563eb); color: #ffffff; font-size: 32px; font-weight: 800; letter-spacing: 8px; padding: 20px 36px; border-radius: 16px; font-family: 'SF Mono', monospace;">
            {code}
          </div>
        </div>
        <p style="font-size: 14px; line-height: 1.6; color: #64748b; text-align: center;">
          This code will expire in <strong>15 minutes</strong>.
        </p>
        <p style="font-size: 13px; line-height: 1.6; color: #94a3b8; margin-top: 32px; text-align: center;">
          If you didn't request a password reset, you can safely ignore this email.
        </p>
      </div>
    </body>
    </html>
    """
    text_body = f"""{greeting}

We received a request to reset your Pivot password.

Your verification code is: {code}

This code will expire in 15 minutes.

If you didn't request a password reset, you can safely ignore this email.
"""
    return text_body, html_body


DEFAULT_EMAIL_FROM = 'Pivot <noreply@internmatch.blog>'


def send_reset_email(to_email: str, code: str, user_name: str = None) -> bool:
    """Send a password reset email via Resend HTTP API.

    Railway blocks outbound SMTP; Resend uses HTTPS and works on Railway.

    Env vars:
      RESEND_API_KEY  — required in production
      EMAIL_FROM      — optional override; defaults to Pivot <noreply@internmatch.blog>

    Without RESEND_API_KEY, logs the code (local/dev fallback) and returns True.
    """
    api_key = (os.environ.get('RESEND_API_KEY') or '').strip()
    from_addr = (os.environ.get('EMAIL_FROM') or '').strip() or DEFAULT_EMAIL_FROM

    text_body, html_body = _build_email_bodies(code, user_name)
    subject = 'Your Pivot Password Reset Code'

    # Local/dev fallback when Resend is not configured
    if not api_key:
        print(f"\n{'=' * 50}")
        print(f'[DEV] RESEND_API_KEY not set — password reset code for {to_email}: {code}')
        print(f"{'=' * 50}\n")
        return True

    try:
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': from_addr,
                'to': [to_email],
                'subject': subject,
                'html': html_body,
                'text': text_body,
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            print(f'[Email] Resend error {resp.status_code} for {to_email}: {resp.text}')
            return False
        return True
    except BaseException as e:
        print(f'[Email] Failed to send reset email to {to_email}: {type(e).__name__}: {e}')
        return False
