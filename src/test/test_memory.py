
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
