import sqlite3

import pytest

from scripts.sqlite_backup import backup, restore


def source(tmp_path):
    path = tmp_path / 'mosto_test_source.db'
    with sqlite3.connect(path) as db:
        db.executescript('''PRAGMA journal_mode=WAL;
          CREATE TABLE alembic_version(version_num TEXT PRIMARY KEY);
          INSERT INTO alembic_version VALUES ('test-revision');
          CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT);
          INSERT INTO sample VALUES (1, 'original');''')
    return path


def test_backup_restore_keeps_snapshot_after_original_changes(tmp_path):
    path = source(tmp_path); archive = tmp_path/'snapshot.db'
    manifest = backup(path, archive)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE sample SET value='changed'")
    target = tmp_path/'mosto_demo_restored.db'
    assert restore(archive,target)['row_counts'] == manifest['row_counts']
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT value FROM sample').fetchone()[0] == 'original'
    with pytest.raises(FileExistsError):
        restore(archive,target)
    with pytest.raises(FileExistsError):
        backup(path,archive)


def test_corruption_and_nonisolated_names_are_rejected(tmp_path):
    path=source(tmp_path); archive=tmp_path/'snapshot.db'
    backup(path,archive)
    with pytest.raises(ValueError,match='local'):
        restore(archive,tmp_path/'production.db')
    with archive.open('ab') as output:
        output.write(b'corrupted')
    target=tmp_path/'mosto_test_restored.db'
    with pytest.raises(ValueError,match='hash'):
        restore(archive,target)
    assert not target.exists()


def test_invalid_database_never_leaves_destination(tmp_path):
    path=tmp_path/'mosto_test_empty.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE not_migrated(id INTEGER)')
    archive=tmp_path/'snapshot.db'
    with pytest.raises(ValueError,match='migration'):
        backup(path,archive)
    assert not archive.exists()


def test_current_mosto_schema_can_be_restored(tmp_path):
    from app.database import engine
    if engine.dialect.name != 'sqlite':
        pytest.skip('This local-store backup contract is SQLite only')
    archive=tmp_path/'snapshot.db'
    result=backup(engine.url.database,archive)
    assert len(result['row_counts']) >= 30
    assert result['row_counts']['USUARIO'] > 0
    target=tmp_path/'mosto_test_restored.db'
    assert restore(archive,target)['row_counts'] == result['row_counts']
