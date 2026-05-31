from django.db import connection
from django.test import TestCase

from rag.sqlite_vector_extension import (
    get_sqlite_vector_extension_path,
    get_sqlite_vector_version,
)


class SQLiteVectorExtensionTests(TestCase):
    def test_extension_path_is_resolvable(self):
        extension_path = get_sqlite_vector_extension_path()

        self.assertTrue(extension_path.endswith("vector"))

    def test_extension_is_loaded_for_django_sqlite_connections(self):
        connection.close()

        version = get_sqlite_vector_version()

        self.assertRegex(version, r"^\d+\.\d+\.\d+")

    def test_vector_search_functions_are_available(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE vector_probe_chunks (
                    id INTEGER PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    label TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO vector_probe_chunks (embedding, label)
                VALUES (vector_as_f32(?), ?)
                """,
                ("[0.1, 0.2, 0.3]", "near"),
            )
            cursor.execute(
                """
                INSERT INTO vector_probe_chunks (embedding, label)
                VALUES (vector_as_f32(?), ?)
                """,
                ("[0.9, 0.8, 0.7]", "far"),
            )
            cursor.execute(
                """
                SELECT vector_init(
                    'vector_probe_chunks',
                    'embedding',
                    'dimension=3,type=FLOAT32,distance=L2'
                )
                """
            )
            cursor.execute(
                """
                SELECT c.label
                FROM vector_full_scan(
                    'vector_probe_chunks',
                    'embedding',
                    vector_as_f32(?),
                    1
                ) AS v
                JOIN vector_probe_chunks c ON c.rowid = v.rowid
                """,
                ("[0.1, 0.2, 0.3]",),
            )
            row = cursor.fetchone()

        self.assertEqual(row, ("near",))
