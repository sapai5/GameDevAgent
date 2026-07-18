from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamedev_agent.memory import SqliteMemoryStore
from gamedev_agent.storage import StateError


class SqliteMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = SqliteMemoryStore(self.root / "memory.sqlite")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_initialization_is_idempotent_and_tracks_schema_version(self) -> None:
        self.assertEqual((1,), self.store.initialize())
        self.assertEqual((), self.store.initialize())
        self.assertEqual(1, self.store.schema_version())
        with self.store.connect() as connection:
            tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
        self.assertTrue(
            {
                "knowledge_sources",
                "knowledge_documents",
                "knowledge_chunks",
                "knowledge_chunks_fts",
                "knowledge_edges",
                "retrieval_traces",
                "hardware_samples",
            }
            <= tables
        )

    def test_foreign_keys_and_fts_follow_chunk_lifecycle(self) -> None:
        self.store.initialize()
        with self.store.connect() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO knowledge_documents(
                        document_id, source_id, title, content_checksum
                    ) VALUES ('missing-doc', 'missing-source', 'Missing', 'sha256:none')
                    """
                )

            connection.execute(
                """
                INSERT INTO knowledge_sources(
                    source_id, canonical_uri, source_kind, content_checksum
                ) VALUES ('blender-docs', 'https://docs.blender.org/', 'documentation', 'sha256:a')
                """
            )
            connection.execute(
                """
                INSERT INTO knowledge_documents(
                    document_id, source_id, title, content_checksum
                ) VALUES ('terrain-doc', 'blender-docs', 'Terrain', 'sha256:b')
                """
            )
            connection.execute(
                """
                INSERT INTO knowledge_chunks(
                    chunk_id, document_id, chunk_index, content, token_count
                ) VALUES ('terrain-0', 'terrain-doc', 0, 'terrain displacement geometry nodes', 4)
                """
            )
            hit = connection.execute(
                "SELECT chunk_id FROM knowledge_chunks_fts WHERE content MATCH 'displacement'"
            ).fetchone()
            self.assertEqual("terrain-0", hit["chunk_id"])

            connection.execute(
                "UPDATE knowledge_chunks SET content = 'water shader nodes' "
                "WHERE chunk_id = 'terrain-0'"
            )
            old_hit = connection.execute(
                "SELECT chunk_id FROM knowledge_chunks_fts WHERE content MATCH 'displacement'"
            ).fetchone()
            new_hit = connection.execute(
                "SELECT chunk_id FROM knowledge_chunks_fts WHERE content MATCH 'shader'"
            ).fetchone()
            self.assertIsNone(old_hit)
            self.assertEqual("terrain-0", new_hit["chunk_id"])

            connection.execute("DELETE FROM knowledge_chunks WHERE chunk_id = 'terrain-0'")
            deleted = connection.execute(
                "SELECT chunk_id FROM knowledge_chunks_fts WHERE content MATCH 'shader'"
            ).fetchone()
            self.assertIsNone(deleted)

    def test_migration_checksum_drift_is_rejected(self) -> None:
        migrations = self.root / "migrations"
        migrations.mkdir()
        migration = migrations / "0001_test.sql"
        migration.write_text("CREATE TABLE example(id INTEGER PRIMARY KEY);\n")
        store = SqliteMemoryStore(self.root / "custom.sqlite", migration_directory=migrations)
        self.assertEqual((1,), store.initialize())
        migration.write_text("CREATE TABLE changed(id INTEGER PRIMARY KEY);\n")
        with self.assertRaisesRegex(StateError, "migration checksum drift"):
            store.initialize()

    def test_missing_migration_directory_is_actionable(self) -> None:
        store = SqliteMemoryStore(
            self.root / "missing.sqlite", migration_directory=self.root / "missing"
        )
        with self.assertRaisesRegex(StateError, "migration directory does not exist"):
            store.initialize()


if __name__ == "__main__":
    unittest.main()
