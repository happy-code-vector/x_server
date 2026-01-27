"""
Helper script to initialize all databases
Run this script before starting the server for the first time
"""
import asyncio
from database_manager import DatabaseManager


async def main():
    print("Initializing databases...")
    db_manager = DatabaseManager()

    for db_config in db_manager.databases:
        print(f"\nInitializing database: {db_config['name']}")
        try:
            await db_manager.initialize_database(db_config)
            print(f"✓ Successfully initialized {db_config['name']}")
        except Exception as e:
            print(f"✗ Error initializing {db_config['name']}: {e}")

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
