from app.database import Base, engine


def main() -> None:
    # Lightweight migration bootstrap for current schema. For larger teams,
    # replace with full Alembic revision workflows.
    Base.metadata.create_all(bind=engine)
    print("Schema ensured with Base.metadata.create_all")


if __name__ == "__main__":
    main()
