#!/usr/bin/env python3
"""
Migration script to add resume_file_path column to user_profiles table.

Run this script if you're upgrading from a previous version:
    python scripts/migrate_add_resume_path.py
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate():
    """Add resume_file_path column to user_profiles table if it doesn't exist."""
    db_path = Path("job_pipeline.db")

    if not db_path.exists():
        print("Database not found. It will be created with the new schema on first run.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [col[1] for col in cursor.fetchall()]

        if "resume_file_path" in columns:
            print("Column 'resume_file_path' already exists. No migration needed.")
            return

        # Add the new column
        print("Adding 'resume_file_path' column to user_profiles table...")
        cursor.execute("""
            ALTER TABLE user_profiles
            ADD COLUMN resume_file_path VARCHAR(500)
        """)
        conn.commit()
        print("Migration successful!")

        # Check if there are existing resume files to link
        resume_dir = Path("resumes")
        if resume_dir.exists():
            resume_files = sorted(resume_dir.glob("resume_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if resume_files:
                latest_resume = str(resume_files[0])
                print(f"Found existing resume: {latest_resume}")

                # Update user profile with the resume path
                cursor.execute("""
                    UPDATE user_profiles
                    SET resume_file_path = ?
                    WHERE id = 1
                """, (latest_resume,))
                conn.commit()
                print(f"Updated user profile with resume path: {latest_resume}")

    except sqlite3.Error as e:
        print(f"Migration error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
