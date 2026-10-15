import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="portal_user",
        password="YourNewPassword123",  # Use the password you set
        database="smart_emergency_portal"  # Corrected spelling here
    )

try:
    conn = get_connection()
    if conn.is_connected():
        print("MySQL Database Connected Successfully!")
except Exception as e:
    print("Connection Error:", e)