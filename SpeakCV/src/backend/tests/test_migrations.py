from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.database import sql_models  # noqa: F401
from app.database.database import Base
from app.database.migrate import BASELINE_REVISION, run_migrations


def _new_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path}/migrate.db")


def test_upgrade_creates_all_tables_on_an_empty_database(tmp_path):
    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "user_profiles", "interview_history", "alembic_version"} <= tables


def test_head_matches_models(tmp_path):
    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": False})
        diffs = compare_metadata(context, Base.metadata)
    assert diffs == []


def test_existing_database_is_stamped_and_keeps_its_data(tmp_path):
    engine = _new_engine(tmp_path)
    legacy_tables = [t for name, t in Base.metadata.tables.items() if name in BASELINE_TABLES]
    Base.metadata.create_all(engine, tables=legacy_tables)
    with engine.begin() as connection:
        # A database from before this column was added, as on a live server.
        connection.execute(text("ALTER TABLE users DROP COLUMN must_change_password"))
        connection.execute(text("ALTER TABLE users DROP COLUMN password_changed_at"))
        connection.execute(text("INSERT INTO users (email, full_name, hashed_password) VALUES ('keep@example.test', 'K', 'h')"))

    with engine.begin() as connection:
        run_migrations(connection)

    with engine.connect() as connection:
        version_rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        kept = connection.execute(text("SELECT email FROM users")).fetchall()
    assert len(version_rows) == 1
    assert version_rows[0][0] >= BASELINE_REVISION
    assert kept == [("keep@example.test",)]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT must_change_password FROM users")).scalar() in (0, False)
        assert connection.execute(text("SELECT password_changed_at FROM users")).scalar() is None


def test_running_twice_is_safe(tmp_path):
    engine = _new_engine(tmp_path)
    for _ in range(2):
        with engine.begin() as connection:
            run_migrations(connection)


BASELINE_TABLES = {
    "users", "user_profiles", "experiences", "educations", "interview_history", "jd_templates",
    "system_config", "transaction_history", "support_messages", "transactions", "company_questions",
    "ai_brain_versions", "ai_brain_nodes", "ai_brain_edges", "ai_brain_ingestion_jobs",
    "ai_brain_ingestion_candidates", "ai_brain_ingestion_files",
}


def test_foreign_keys_to_users_from_the_brain_set_null(tmp_path):
    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    inspector = inspect(engine)
    for table, column in (
        ("kb_documents", "uploaded_by"), ("kb_nodes", "approved_by"), ("kb_conflicts", "resolved_by"),
        ("assistant_questions", "user_id"),
    ):
        [key] = [k for k in inspector.get_foreign_keys(table) if k["constrained_columns"] == [column]]
        assert key["options"].get("ondelete") == "SET NULL", table
        [model_key] = Base.metadata.tables[table].c[column].foreign_keys
        assert model_key.ondelete == "SET NULL", table


def test_there_is_one_head_and_it_is_the_hiring_migration():
    from alembic.script import ScriptDirectory

    from app.database.migrate import alembic_config

    assert ScriptDirectory.from_config(alembic_config()).get_heads() == ["0006_hiring"]
