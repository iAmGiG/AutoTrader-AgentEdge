# memory_system.py
"""
A simple memory system for the multi-agent infrastructure.

This implementation provides an EphemeralMemory layer for short-term data storage,
with support for optional TTL (time-to-live) on entries. Future enhancements can add
context (mid-term) and persistent (long-term) memory layers.
"""

import time
import threading


class EphemeralMemory:
    def __init__(self, ttl: float = None):
        """
        Initialize the in-memory store.

        :param ttl: Optional time-to-live (in seconds) for each entry.
        """
        self.data = {}  # Dictionary to hold memory entries.
        self.ttl = ttl  # Time-to-live in seconds.
        self.lock = threading.Lock()

    def store_data(self, key: str, value: any) -> None:
        """
        Store data with the current timestamp.

        :param key: Unique identifier for the entry.
        :param value: Data to store.
        """
        with self.lock:
            entry = {"value": value, "timestamp": time.time()}
            self.data[key] = entry

    def retrieve_data(self, key: str) -> any:
        """
        Retrieve data for the given key. If TTL is set and the entry has expired,
        it will be removed and None is returned.

        :param key: Unique identifier for the entry.
        :return: Stored value or None if not found or expired.
        """
        with self.lock:
            entry = self.data.get(key)
            if entry:
                if self.ttl is not None:
                    if time.time() - entry["timestamp"] > self.ttl:
                        del self.data[key]
                        return None
                return entry["value"]
            return None

    def cleanup(self) -> None:
        """
        Remove expired entries if TTL is set.
        """
        if self.ttl is None:
            return
        with self.lock:
            current_time = time.time()
            keys_to_delete = [k for k, entry in self.data.items()
                              if current_time - entry["timestamp"] > self.ttl]
            for k in keys_to_delete:
                print(f"Removing expired key: {k}")  # Debug print
                del self.data[k]


class MemorySystem:
    """
    MemorySystem aggregates different memory layers. Currently, it only implements
    an EphemeralMemory layer for rapid, short-term storage. Future enhancements can
    include context and persistent memory layers.
    """

    def __init__(self, ttl: float = None):
        # Initialize the ephemeral memory layer.
        self.ephemeral = EphemeralMemory(ttl=ttl)
        # Placeholders for future memory layers:
        # self.context = ContextMemory()
        # self.persistent = PersistentMemory()

    def store_data(self, key: str, data: any, layer: str = 'ephemeral') -> None:
        """
        Store data in the specified memory layer.

        :param key: Unique identifier for the data.
        :param data: Data to store.
        :param layer: The memory layer to use ('ephemeral' by default).
        """
        if layer == 'ephemeral':
            self.ephemeral.store_data(key, data)
        else:
            raise NotImplementedError(
                f"Memory layer '{layer}' is not implemented yet.")

    def retrieve_data(self, key: str, layer: str = 'ephemeral') -> any:
        """
        Retrieve data from the specified memory layer.

        :param key: Unique identifier for the data.
        :param layer: The memory layer to access ('ephemeral' by default).
        :return: The stored data, or None if not found.
        """
        if layer == 'ephemeral':
            return self.ephemeral.retrieve_data(key)
        else:
            raise NotImplementedError(
                f"Memory layer '{layer}' is not implemented yet.")

    def cleanup(self) -> None:
        """
        Perform cleanup operations for all memory layers.
        """
        self.ephemeral.cleanup()
        # In the future, add cleanup for context and persistent memory.


# For testing purposes (run this file directly to test basic functionality)
if __name__ == "__main__":
    mem_sys = MemorySystem(ttl=5)  # Entries expire after 5 seconds
    mem_sys.store_data("example_key", {"data": "This is a test."})
    print("Stored data:", mem_sys.retrieve_data("example_key"))
    time.sleep(6)
    print("After TTL, retrieved data:", mem_sys.retrieve_data("example_key"))
