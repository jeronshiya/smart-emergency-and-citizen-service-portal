## MySQL setup

Install and start MySQL Server, then create the application database and a
dedicated local account from a MySQL administrator session. Replace the
example password with a strong password:

```sql
CREATE DATABASE IF NOT EXISTS smart_emergency_portal;
CREATE USER IF NOT EXISTS 'portal_user'@'localhost' IDENTIFIED BY 'ChangeThisPassword';
CREATE USER IF NOT EXISTS 'portal_user'@'127.0.0.1' IDENTIFIED BY 'ChangeThisPassword';
ALTER USER 'portal_user'@'localhost' IDENTIFIED BY 'ChangeThisPassword';
ALTER USER 'portal_user'@'127.0.0.1' IDENTIFIED BY 'ChangeThisPassword';
GRANT ALL PRIVILEGES ON smart_emergency_portal.* TO 'portal_user'@'localhost';
GRANT ALL PRIVILEGES ON smart_emergency_portal.* TO 'portal_user'@'127.0.0.1';
FLUSH PRIVILEGES;

USE smart_emergency_portal;

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    mobile VARCHAR(30) NOT NULL,
    password VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL DEFAULT '',
    city VARCHAR(100) NOT NULL DEFAULT '',
    pincode VARCHAR(20) NOT NULL DEFAULT '',
    category VARCHAR(50) NOT NULL DEFAULT 'Citizen',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Set the connection settings in the same PowerShell window used to start Flask:

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_USER = "portal_user"
$env:DB_PASSWORD = "ChangeThisPassword"
$env:DB_NAME = "smart_emergency_portal"
```

`DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` can be used to override the
defaults in `database.py`. Restart Flask after setting them. Error 1130 means
the MySQL server does not permit a connection from that host; verify that the
SQL ran on the same MySQL instance the app is connecting to.

If MySQL reports error 1045 for `portal_user`, the account password may differ
from `DB_PASSWORD`. `CREATE USER IF NOT EXISTS` does not change the password of
an account that already exists, so run the `ALTER USER` statements above in a
MySQL administrator session, replacing the example password with the same
strong password configured in `DB_PASSWORD`, then restart Flask.

## Saving nearby places

Log in to your citizen account and use the **Save** button on a nearby hospital
or blood bank. Saved places are linked to your account and available from
**My Saved Places** on the dashboard. The app creates the `saved_facilities`
table automatically when it is first needed; the database account therefore
needs permission to create tables.

## Complaint email notification

After a complaint is saved, the app emails the admin and the citizen's registered email address. Configure these variables in the same PowerShell window before starting Flask:

```powershell
$env:SMTP_USER = "your-gmail@gmail.com"
$env:SMTP_PASSWORD = "your-gmail-app-password"
$env:ADMIN_EMAIL = "admin@example.com"
```

Optional settings are `SMTP_HOST` and `SMTP_PORT`; they default to Gmail SMTP on port 587. For Gmail, use a Google App Password, not your normal account password. Restart Flask after setting these variables.

For an SMS confirmation to the citizen's registered mobile number, configure a Twilio SMS-capable number and set these variables:

```powershell
$env:TWILIO_ACCOUNT_SID = "your-account-sid"
$env:TWILIO_AUTH_TOKEN = "your-auth-token"
$env:TWILIO_SMS_FROM_NUMBER = "+1xxxxxxxxxx"
$env:DEFAULT_COUNTRY_CODE = "+91"
```

Email and SMS notifications are optional; complaints are still saved if either provider is not configured or a notification fails.

```powershell
$env:SMTP_USER = "your-gmail@gmail.com"
$env:SMTP_PASSWORD = "your-gmail-app-password"
$env:ADMIN_EMAIL = "admin@example.com"
```

Optional settings are `SMTP_HOST` and `SMTP_PORT`; they default to Gmail SMTP on port 587. Use a Gmail App Password, not the normal Gmail password.

## SOS confirmation calls

The app can call the citizen after an SOS is saved. Configure a Twilio voice-enabled number and set these variables before starting Flask:

```powershell
$env:TWILIO_ACCOUNT_SID = "your-account-sid"
$env:TWILIO_AUTH_TOKEN = "your-auth-token"
$env:TWILIO_FROM_NUMBER = "+1xxxxxxxxxx"
$env:DEFAULT_COUNTRY_CODE = "+91"
$env:PUBLIC_BASE_URL = "https://your-public-https-domain.example"
$env:TWILIO_SMS_FROM_NUMBER = "+1xxxxxxxxxx"
$env:POLICE_PHONE = "+919xxxxxxxxx"
$env:AMBULANCE_PHONE = "+919xxxxxxxxx"
```

The citizen can press `1` to confirm that help is required or `2` to deny the incident. A phone response is recorded as a user confirmation only; an admin, responder, or police confirmation is still required before marking an SOS as `Verified`. For local testing, expose the Flask server through an HTTPS tunnel so Twilio can reach the confirmation webhook.

Admins can forward an SOS to police or ambulance from the SOS management page. The dispatch status is tracked as `SENT`, `DELIVERED`, `UNDELIVERED`, or `FAILED`. The forwarded message contains a secure responder link where the receiving team can update `ACKNOWLEDGED`, `ON_THE_WAY`, `ARRIVED`, or `COMPLETED`.
