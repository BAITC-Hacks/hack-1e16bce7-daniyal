from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.infrastructure.database import Base

# Import future ORM models here so their tables register in Base.metadata.
target_metadata = Base.metadata
url = Settings().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 3})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
