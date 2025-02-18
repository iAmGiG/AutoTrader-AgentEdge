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
    def __init__(self, ttl: float = None, lazy_eviction: bool = True, refresh_on_access: bool = False):
        """
        :param ttl: Optional time-to-live (in seconds).
        :param lazy_eviction: If True, remove expired entries only on access.
        :param refresh_on_access: If True, any read operation resets the timestamp if data hasn't expired yet.
        """
        self.data = {}
        self.ttl = ttl
        self.lock = threading.Lock()
        self.lazy_eviction = lazy_eviction
        self.refresh_on_access = refresh_on_access

    def store_data(self, key: str, value: any) -> None:
        with self.lock:
            entry = {
                "value": value,
                "timestamp": time.time()
            }
            self.data[key] = entry
            logger.info(f"EphemeralMemory: Stored key '{key}'.")

    def retrieve_data(self, key: str) -> any:
        with self.lock:
            entry = self.data.get(key)
            if not entry:
                return None

            # Check TTL
            elapsed = time.time() - entry["timestamp"]
            if self.ttl is not None and elapsed > self.ttl:
                # Expired, remove it
                logger.info(
                    f"EphemeralMemory: Key '{key}' expired on access. Removing entry.")
                del self.data[key]
                return None

            # Refresh TTL upon read
            if self.refresh_on_access and self.ttl is not None:
                entry["timestamp"] = time.time()
                logger.info(
                    f"EphemeralMemory: Key '{key}' timestamp refreshed.")

            return entry["value"]

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
    Minimal persistent memory using the same SQLite file (or in-memory DB).
    This can later be expanded for advanced retrieval.
    """

    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self.conn = conn
        self.lock = lock
        self._setup_schema()

    def _setup_schema(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persistent_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp REAL
                )
            """)
            self.conn.commit()

    def store_data(self, key: str, value: any) -> None:
        with self.lock:
            timestamp = time.time()
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO persistent_memory (key, value, timestamp)
                VALUES (?, ?, ?)
            """, (key, str(value), timestamp))
            self.conn.commit()
            logger.info(f"PersistentMemory: Stored key '{key}'.")

    def retrieve_data(self, key: str) -> any:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT value FROM persistent_memory WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def cleanup(self):
        """
        (Optional) Implement any cleanup if needed for long-term data,
        such as removing data older than a certain threshold.
        """
        pass


class MemorySystem:
    def __init__(self, ephemeral_ttl: float = None, context_db_path: str = ":memory:"):
        self.ephemeral = EphemeralMemory(
            ttl=ephemeral_ttl, refresh_on_access=True)
        self.ephemeral.start_periodic_cleanup()

        # Set up a single SQLite connection and lock for both context & persistent
        self.conn = sqlite3.connect(context_db_path, check_same_thread=False)
        self.lock = threading.Lock()

        self.context = ContextMemory(db_path=context_db_path)

        # Reuse the same connection & lock for persistent memory
        self.persistent = PersistentMemory(conn=self.conn, lock=self.lock)

    def store_data(self, key: str, data: any, layer: str = 'ephemeral') -> None:
        if layer == 'ephemeral':
            self.ephemeral.store_data(key, data)
        elif layer == 'context':
            self.context.store_data(key, str(data))
        elif layer == 'persistent':
            self.persistent.store_data(key, data)
        else:
            raise ValueError(f"Unknown memory layer: {layer}")

    def retrieve_data(self, key: str, layer: str = 'ephemeral') -> any:
        if layer == 'ephemeral':
            return self.ephemeral.retrieve_data(key)
        elif layer == 'context':
            return self.context.retrieve_data(key)
        elif layer == 'persistent':
            return self.persistent.retrieve_data(key)
        else:
            raise ValueError(f"Unknown memory layer: {layer}")

    def cleanup_all(self):
        self.ephemeral.cleanup()
        self.context.cleanup()
        # Optional: self.persistent.cleanup() if you want a retention policy for persistent data.


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
