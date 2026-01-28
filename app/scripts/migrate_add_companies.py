"""Migration script to add companies table and new profile preference fields."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.db import init_db, engine
from app.models import Base, Company


def run_migration():
    """Run migration to add companies table and new profile fields."""

    # Parse database URL to get SQLite file path
    db_url = config.database.url
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        print(f"Error: Only SQLite databases supported. Got: {db_url}")
        return False

    print(f"Running migration on database: {db_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if companies table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
        companies_exists = cursor.fetchone() is not None

        if not companies_exists:
            print("✓ Companies table doesn't exist yet, will be created by init_db()")
        else:
            print("✓ Companies table already exists")

        # Check if new columns exist in user_profiles
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        new_columns = [
            "preferred_industries",
            "preferred_company_sizes",
            "preferred_company_stages",
            "preferred_tech_stack"
        ]

        for col_name in new_columns:
            if col_name not in columns:
                print(f"Adding column {col_name} to user_profiles...")
                cursor.execute(f"ALTER TABLE user_profiles ADD COLUMN {col_name} JSON")
                print(f"✓ Added {col_name}")
            else:
                print(f"✓ Column {col_name} already exists")

        conn.commit()
        print("\n✓ Migration completed successfully")

        # Now create any missing tables (like companies)
        print("\nCreating any missing tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ All tables created/verified")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
