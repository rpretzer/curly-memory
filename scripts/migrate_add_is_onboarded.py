import sqlite3
import os

DB_PATH = "job_pipeline.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "is_onboarded" in columns:
            print("Column 'is_onboarded' already exists. No migration needed.")
        else:
            print("Adding 'is_onboarded' column to user_profiles table...")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN is_onboarded BOOLEAN DEFAULT 0")
            print("Migration successful.")
            
        conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
