from alembic import context

from app.database import sql_models  # noqa: F401
from app.database.database import Base, engine

target_metadata = Base.metadata


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with engine.connect() as new_connection:
        _run(new_connection)
        new_connection.commit()


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")
run_migrations_online()
