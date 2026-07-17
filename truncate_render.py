from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg://remotehubnew:mTGlkCCChHBH2iKDA3LEp3JdcqSZHn4X@dpg-d9ac0pucjfls739jobe0-a.oregon-postgres.render.com/remotehub_c4lt"

TABLES = ["audit_logs", "chat_messages", "commands", "machine_access", "pairing_codes", "machines", "users"]

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    for table in TABLES:
        try:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            conn.commit()
            print(f"Truncated: {table}")
        except Exception as exc:
            conn.rollback()
            print(f"Skipped {table}: {exc.__class__.__name__} - {exc}")

    print("\nFinal counts:")
    for table in TABLES:
        try:
            result = conn.execute(text(f"SELECT count(*) FROM {table}"))
            print(f"  {table}: {result.scalar()}")
        except Exception:
            conn.rollback()
            print(f"  {table}: (table doesn't exist)")