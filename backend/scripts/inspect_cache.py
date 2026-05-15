"""Quick cache inspector — prints every row in the SQLite cache."""
import sqlite3
import sys

sys.path.insert(0, sys.path[0] + "/..")
import cache

cache.init_db()
conn = sqlite3.connect(cache._db_path())
rows = conn.execute(
    "SELECT substr(key,1,16) AS key_prefix, "
    "length(value) AS bytes, "
    "datetime(created_at,'unixepoch') AS created, "
    "datetime(expires_at,'unixepoch') AS expires "
    "FROM cache ORDER BY created_at DESC"
).fetchall()

print(f"{len(rows)} cache row(s):\n")
for key_prefix, size, created, expires in rows:
    print(f"  {key_prefix}...  {size:>7} bytes  created={created}  expires={expires}")
