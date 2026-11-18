"""Verified SQLite backup/restore for explicitly named local demo/test stores.

Never reads .env or uses a remote database. Existing destinations are refused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing


def local_store(path):
    path = Path(path).resolve()
    if path.suffix not in {'.db', '.sqlite3'} or not path.name.startswith(('mosto_demo', 'mosto_test')):
        raise ValueError('Use a local mosto_demo*.db or mosto_test*.db store')
    return path


def open_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def evidence(connection):
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('SQLite integrity check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('SQLite foreign key check failed')
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if 'alembic_version' not in tables:
        raise ValueError('Missing migration metadata')
    versions = [r[0] for r in connection.execute('SELECT version_num FROM alembic_version')]
    if not versions:
        raise ValueError('Empty migration metadata')
    counts = {}
    for table in tables:
        name = '"' + table.replace('"', '""') + '"'
        counts[table] = connection.execute('SELECT count(*) FROM ' + name).fetchone()[0]
    return dict(migrations=sorted(versions), row_counts=counts)


def copy_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('Source and destination must differ')
    # Exclusive creation prevents a stale CLI invocation overwriting any store.
    with destination.open('xb'):
        pass
    try:
        with closing(open_readonly(source)) as original:
            with closing(sqlite3.connect(destination)) as copy:
                original.backup(copy)
                result = evidence(copy)
        return result
    except Exception:
        destination.unlink(missing_ok=True)  # Only the file exclusively created above.
        raise


def backup(source, archive):
    source, archive = local_store(source), Path(archive).resolve()
    manifest = Path(str(archive) + '.json')
    if manifest.exists():
        raise FileExistsError('Backup manifest already exists')
    result = copy_database(source, archive)
    result.update(format='mosto-sqlite-backup-v1', sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    with manifest.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    return result


def restore(archive, destination):
    archive, destination = Path(archive).resolve(), local_store(destination)
    manifest = json.loads(Path(str(archive) + '.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'mosto-sqlite-backup-v1' or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest.get('sha256'):
        raise ValueError('Backup manifest or hash mismatch')
    # Validate the archived snapshot before creating a destination.
    with closing(open_readonly(archive)) as source:
        expected = evidence(source)
    if expected != {k: manifest.get(k) for k in ('migrations', 'row_counts')}:
        raise ValueError('Backup evidence mismatch')
    result = copy_database(archive, destination)
    if result != expected:
        raise ValueError('Restored evidence mismatch; retain destination for diagnosis')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = (backup if args.action == 'backup' else restore)(args.source, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
