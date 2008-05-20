# Django settings for buildbotcustom project.

DATABASE_ENGINE = 'sqlite3'    # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = 'builds.db' # Or path to database file if using sqlite3.

INSTALLED_APPS = (
  'buildbotcustom.builds',
)
