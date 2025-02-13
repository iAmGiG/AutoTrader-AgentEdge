# memory_system.py
"""
Revised Memory System for Multi-Agent Infrastructure

This module implements a hierarchical memory system with three layers:
  1. EphemeralMemory: Short-term in-memory storage with TTL-based lazy eviction.
  2. ContextMemory: Mid-term storage using SQLite for transactional context data.
  3. PersistentMemory: A stub for long-term storage (to be extended as needed).

It includes enhanced logging, concurrency controls, and periodic cleanup.
"""

import time
import threading
import logging
import sqlite3

# Configure logging for the module.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EphemeralMemory:
    def __init__(self, ttl: float = None, lazy_eviction: bool = True):
        """
        Initialize the in-memory ephemeral storage.

        :param ttl: Optional time-to-live (in seconds) for each entry.
        :param lazy_eviction: If True, expired entries are evicted upon access.
        """
        self.data = {}  # Dictionary to store entries.
        self.ttl = ttl  # Time-to-live in seconds.
        self.lock = threading.Lock()
        self.lazy_eviction = lazy_eviction

    def store_data(self, key: str, value: any) -> None:
        """
        Store a key-value pair with the current timestamp.

        :param key: Unique identifier for the data.
        :param value: Data to store.
        """
        with self.lock:
            entry = {"value": value, "timestamp": time.time()}
            self.data[key] = entry
            logger.info(f"EphemeralMemory: Stored key '{key}'.")

    def retrieve_data(self, key: str) -> any:
        """
        Retrieve data by key with lazy eviction.

        If the data has expired based on TTL, it is removed and None is returned.

        :param key: Unique identifier for the data.
        :return: The stored value or None if not found/expired.
        """
        with self.lock:
            entry = self.data.get(key)
            if entry:
                if self.ttl is not None and (time.time() - entry["timestamp"]) > self.ttl:
                    logger.info(
                        f"EphemeralMemory: Key '{key}' expired on access. Removing entry.")
                    del self.data[key]
                    return None
                return entry["value"]
            return None

    def cleanup(self) -> None:
        """
        Actively clean up expired entries based on TTL.
        """
        if self.ttl is None:
            return
        with self.lock:
            current_time = time.time()
            keys_to_delete = [k for k, entry in self.data.items()
                              if current_time - entry["timestamp"] > self.ttl]
            for k in keys_to_delete:
                logger.info(f"EphemeralMemory: Cleaning up expired key '{k}'.")
                del self.data[k]

    def start_periodic_cleanup(self, interval: float = 10.0):
        """
        Start a background thread to periodically clean up expired entries.

        :param interval: Time interval in seconds between cleanups.
        """
        def cleanup_loop():
            while True:
                time.sleep(interval)
                self.cleanup()
        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()


class ContextMemory:
    """
    A basic context memory layer implemented using SQLite.

    This layer is intended for mid-term storage of session or context data.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._setup_schema()

    def _setup_schema(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp REAL
                )
            """)
            self.conn.commit()

    def store_data(self, key: str, value: str) -> None:
        with self.lock:
            timestamp = time.time()
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO context_memory (key, value, timestamp)
                VALUES (?, ?, ?)
            """, (key, value, timestamp))
            self.conn.commit()
            logger.info(f"ContextMemory: Stored key '{key}'.")

    def retrieve_data(self, key: str) -> any:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT value FROM context_memory WHERE key = ?
            """, (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None

    def cleanup(self, max_age: float = 3600):
        """
        Remove entries older than max_age seconds.
        """
        with self.lock:
            cutoff = time.time() - max_age
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM context_memory WHERE timestamp < ?
            """, (cutoff,))
            self.conn.commit()
            logger.info("ContextMemory: Cleanup executed.")


class PersistentMemory:
    """
    A stub for persistent memory storage.

    In a full implementation, integrate with a vector database or another
    long-term storage solution that supports advanced retrieval.
    """

    def __init__(self):
        self.data = {}  # For demonstration purposes.
        self.lock = threading.Lock()

    def store_data(self, key: str, value: any) -> None:
        with self.lock:
            self.data[key] = {"value": value, "timestamp": time.time()}
            logger.info(f"PersistentMemory: Stored key '{key}'.")

    def retrieve_data(self, key: str) -> any:
        with self.lock:
            entry = self.data.get(key)
            if entry:
                return entry["value"]
            return None

    # Future extensions: Implement snapshotting, versioning, and semantic search.


class MemorySystem:
    """
    Unified memory system that aggregates ephemeral, context, and persistent layers.
    """

    def __init__(self, ephemeral_ttl: float = None, context_db_path: str = ":memory:"):
        self.ephemeral = EphemeralMemory(ttl=ephemeral_ttl)
        self.ephemeral.start_periodic_cleanup()  # Start background cleanup.
        self.context = ContextMemory(db_path=context_db_path)
        self.persistent = PersistentMemory()

    def store_data(self, key: str, data: any, layer: str = 'ephemeral') -> None:
        """
        Store data in the specified memory layer.

        :param key: Unique identifier for the data.
        :param data: The data to store.
        :param layer: Memory layer: 'ephemeral', 'context', or 'persistent'.
        """
        if layer == 'ephemeral':
            self.ephemeral.store_data(key, data)
        elif layer == 'context':
            # Convert to string for storage; adapt as needed for complex data.
            self.context.store_data(key, str(data))
        elif layer == 'persistent':
            self.persistent.store_data(key, data)
        else:
            raise ValueError(f"Unknown memory layer: {layer}")

    def retrieve_data(self, key: str, layer: str = 'ephemeral') -> any:
        """
        Retrieve data from the specified memory layer.

        :param key: Unique identifier for the data.
        :param layer: Memory layer: 'ephemeral', 'context', or 'persistent'.
        :return: The stored data, or None if not found.
        """
        if layer == 'ephemeral':
            return self.ephemeral.retrieve_data(key)
        elif layer == 'context':
            return self.context.retrieve_data(key)
        elif layer == 'persistent':
            return self.persistent.retrieve_data(key)
        else:
            raise ValueError(f"Unknown memory layer: {layer}")

    def cleanup_all(self):
        """
        Trigger cleanup for all memory layers.
        """
        self.ephemeral.cleanup()
        self.context.cleanup()
        # PersistentMemory cleanup can be implemented if needed.


# Testing the revised memory system.
if __name__ == "__main__":
    # Create a memory system with a 5-second TTL for ephemeral storage.
    mem_sys = MemorySystem(ephemeral_ttl=5, context_db_path=":memory:")

    # Test Ephemeral Memory
    mem_sys.store_data("ephemeral_key", {
                       "data": "This is a test."}, layer="ephemeral")
    logger.info(
        f"Ephemeral stored data: {mem_sys.retrieve_data('ephemeral_key', layer='ephemeral')}")
    time.sleep(6)
    logger.info(
        f"After TTL, ephemeral data: {mem_sys.retrieve_data('ephemeral_key', layer='ephemeral')}")

    # Test Context Memory
    mem_sys.store_data(
        "context_key", {"data": "Context test data."}, layer="context")
    logger.info(
        f"Context stored data: {mem_sys.retrieve_data('context_key', layer='context')}")

    # Test Persistent Memory
    mem_sys.store_data("persistent_key", {
                       "data": "Persistent test data."}, layer="persistent")
    logger.info(
        f"Persistent stored data: {mem_sys.retrieve_data('persistent_key', layer='persistent')}")
