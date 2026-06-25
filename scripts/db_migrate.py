from sqlalchemy import inspect, text

from app.database import Base, engine


def _ensure_origin_ip_column() -> None:
    inspector = inspect(engine)
    if "mentions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("mentions")}
    if "origin_ip" in columns:
        return
    dialect = engine.dialect.name
    if dialect == "sqlite":
        ddl = "ALTER TABLE mentions ADD COLUMN origin_ip VARCHAR(64) DEFAULT ''"
    else:
        ddl = "ALTER TABLE mentions ADD COLUMN IF NOT EXISTS origin_ip VARCHAR(64) DEFAULT ''"
    with engine.begin() as conn:
        conn.execute(text(ddl))


def main() -> None:
    # Lightweight migration bootstrap for current schema. For larger teams,
    # replace with full Alembic revision workflows.
    Base.metadata.create_all(bind=engine)
    _ensure_origin_ip_column()
    print("Schema ensured with Base.metadata.create_all")


if __name__ == "__main__":
    main()
