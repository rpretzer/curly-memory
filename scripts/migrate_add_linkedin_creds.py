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
        # Check if columns exist
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "linkedin_user" not in columns:
            print("Adding 'linkedin_user' column...")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN linkedin_user VARCHAR(200)")
            
        if "linkedin_password" not in columns:
            print("Adding 'linkedin_password' column...")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN linkedin_password TEXT")
            
        print("Migration successful.")
        conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
