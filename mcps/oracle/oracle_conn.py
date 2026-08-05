import threading
from contextlib import contextmanager

import oracledb

import config

dsn = f"""(DESCRIPTION=
  (CONNECT_TIMEOUT=5)
  (TRANSPORT_CONNECT_TIMEOUT=3)
  (RETRY_COUNT=3)
  (ADDRESS_LIST=
    (LOAD_BALANCE=on)
    (FAILOVER=on)
    (ADDRESS=(PROTOCOL=TCP)(HOST={config.ORACLE_HOST})(PORT={config.ORACLE_PORT}))
  )
  (CONNECT_DATA=(SERVICE_NAME={config.ORACLE_SERVICE_NAME}))
)"""

_pool = None
_pool_lock = threading.Lock()


def _init_session(connection, requested_tag):
    # Unqualified table names in run_query() must resolve to the exposed
    # schema even when connecting as a dedicated read-only user that owns
    # nothing itself. ORACLE_TARGET_SCHEMA is validated as a plain identifier
    # in config.py (identifiers cannot be bound in ALTER SESSION).
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {config.ORACLE_TARGET_SCHEMA}")


def _get_pool():
    """Create the pool on first use, not at import.

    Lazy init keeps a briefly-unreachable database from preventing server
    startup, and keeps this module importable without Instant Client
    installed (FastMCP tools run in worker threads, hence the lock).

    Thick mode is entered only when ORACLE_LIB_DIR is set. Left unset, the
    driver stays in thin mode and no Instant Client is needed.
    """
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if config.ORACLE_LIB_DIR:
                    oracledb.init_oracle_client(lib_dir=config.ORACLE_LIB_DIR)
                oracledb.defaults.fetch_lobs = False
                _pool = oracledb.create_pool(
                    user=config.ORACLE_USER,
                    password=config.ORACLE_PASSWORD,
                    dsn=dsn,
                    min=0,
                    max=5,
                    increment=1,
                    timeout=300,
                    ping_interval=60,
                    session_callback=_init_session,
                )
    return _pool


@contextmanager
def get_connection():
    with _get_pool().acquire() as connection:
        connection.call_timeout = config.QUERY_TIMEOUT_SECONDS * 1000
        yield connection
