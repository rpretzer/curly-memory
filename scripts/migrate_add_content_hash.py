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
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "content_hash" in columns:
            print("Column 'content_hash' already exists. No migration needed.")
        else:
            print("Adding 'content_hash' column to jobs table...")
            cursor.execute("ALTER TABLE jobs ADD COLUMN content_hash VARCHAR(32)")
            # Create index as per model definition
            print("Creating index for 'content_hash'...")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_content_hash ON jobs (content_hash)")
            print("Migration successful.")
            
        conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
