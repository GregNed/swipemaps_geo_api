import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context


config = context.config  # alembic.ini
# Set up logging
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')
# Get a ref to the migrate extension
migrate = current_app.extensions['migrate']
# Specify the database
config.set_main_option('sqlalchemy.url', str(migrate.db.engine.url))
# Specify the tables in models.py to be monitored
target_metadata = migrate.db.metadata
# Ignore 'static' table baked into custom postgis image so alembic doesn't drop them
exclude_tables = config.get_section('exclude').get('tables', '').split(',')


def include_object(_, name, type_, *args):
    """Check if the passed object, e.g. table, is excluded from monitoring."""
    return not (type_ == 'table' and name in exclude_tables)


def run_migrations():
    """Apply migrations directly to the db, rather than generate a SQL script."""
    # Prevent an auto-migration from being generated when there are no changes to the schema
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False) and directives[0].upgrade_ops.is_empty():
            directives[:] = []
            logger.info('No changes detected')

    with migrate.db.engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            include_object=include_object,
            **migrate.configure_args
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
