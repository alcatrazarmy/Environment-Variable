"""
AirtableIO: A helper module for batch operations with Airtable.
"""


class AirtableIO:
    """
    A wrapper class for pyairtable.Table that provides batch operations.
    """

    def __init__(self, table, dedupe_field=None):
        """
        Initialize AirtableIO.

        Args:
            table: A pyairtable.Table instance.
            dedupe_field: Deprecated, use key_field in batch_upsert instead.
        """
        self.table = table

    def batch_upsert(self, rows, key_field, chunk=10):
        """
        Batch upsert rows into Airtable using the specified key field.

        Args:
            rows: List of dictionaries representing records to upsert.
            key_field: The field name to use as the unique key for upserts.
            chunk: Number of records to process in each batch (default: 10).
        """
        if not rows:
            return

        # Process rows in chunks
        for i in range(0, len(rows), chunk):
            batch = rows[i:i + chunk]
            # Use pyairtable's batch_upsert method with key_fields parameter
            self.table.batch_upsert(
                [{"fields": row} for row in batch],
                key_fields=[key_field]
            )
