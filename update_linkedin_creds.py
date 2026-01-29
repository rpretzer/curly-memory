"""
Utility script to update LinkedIn credentials in the database.

Usage:
    python update_linkedin_creds.py <email> <password>

Example:
    python update_linkedin_creds.py user@example.com mypassword
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from app.db import get_db_context
from app.models import UserProfile
from app.security import get_fernet

def update_linkedin_creds(email, password):
    with get_db_context() as db:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not profile:
            print("Error: User profile not found")
            return

        print(f"Updating credentials for profile: {profile.name}")
        
        # Encrypt password
        fernet = get_fernet()
        encrypted_password = fernet.encrypt(password.encode()).decode()
        
        profile.linkedin_user = email
        profile.linkedin_password = encrypted_password
        
        db.commit()
        print("✓ LinkedIn credentials updated successfully in the database")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Update LinkedIn credentials in the database')
    parser.add_argument('email', help='LinkedIn email address')
    parser.add_argument('password', help='LinkedIn password (will be encrypted)')

    args = parser.parse_args()
    update_linkedin_creds(args.email, args.password)
