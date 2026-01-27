#!/usr/bin/env python3
"""
Database Migration Script
Migrates all data from local PostgreSQL databases to an online PostgreSQL database.
"""

import asyncio
import json
import sys
from typing import List, Dict, Optional
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.pool import NullPool
import argparse
from datetime import datetime
from logger import logger


class DatabaseMigrator:
    """Handles migration from local databases to online database"""
    
    def __init__(self, migration_config_path: str = "migration.json"):
        self.migration_config_path = migration_config_path
        self.migration_config = self._load_migration_config()
        self.local_databases = self.migration_config.get("local_databases", [])
        self.online_database = self.migration_config.get("online_database", {})
        self.migration_settings = self.migration_config.get("migration_settings", {})
        self.batch_size = self.migration_settings.get("batch_size", 1000)
        
    def _load_migration_config(self) -> dict:
        """Load migration configuration from JSON file"""
        try:
            with open(self.migration_config_path, 'r') as f:
                config = json.load(f)
                
            # Validate required sections
            if "local_databases" not in config:
                logger.error("Missing 'local_databases' section in migration config")
                sys.exit(1)
            if "online_database" not in config:
                logger.error("Missing 'online_database' section in migration config")
                sys.exit(1)
                
            return config
        except FileNotFoundError:
            logger.error(f"Migration config file {self.migration_config_path} not found")
            logger.error("Please create migration.json file with your database configurations")
            logger.error("See migration.json.example for reference")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in migration config file: {e}")
            sys.exit(1)
    
    def _get_connection_string(self, db_config: dict) -> str:
        """Generate PostgreSQL connection string"""
        return f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
    
    def _get_async_connection_string(self, db_config: dict) -> str:
        """Generate async PostgreSQL connection string"""
        return f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
    
    async def test_connection(self, db_config: dict) -> bool:
        """Test database connection"""
        try:
            conn = await asyncpg.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['name']
            )
            await conn.close()
            logger.info(f"✓ Connection successful to {db_config['host']}:{db_config['port']}/{db_config['name']}")
            return True
        except Exception as e:
            logger.error(f"✗ Connection failed to {db_config['host']}:{db_config['port']}/{db_config['name']}: {e}")
            return False
    
    async def initialize_online_database(self, online_db_config: dict):
        """Initialize online database with required tables and indexes"""
        logger.info("Initializing online database...")
        
        conn_string = self._get_async_connection_string(online_db_config)
        engine = create_async_engine(conn_string, poolclass=NullPool)
        
        try:
            async with engine.connect() as conn:
                # Create tweets table
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tweets (
                        tweet_id            TEXT NOT NULL,
                        username            TEXT,
                        text                TEXT NOT NULL,
                        created_at          TIMESTAMPTZ NOT NULL,
                        tweet_url           TEXT,
                        hashtags            TEXT[],

                        user_id             TEXT,
                        display_name        TEXT,

                        followers_count     INT,
                        following_count     INT,
                        verified            BOOLEAN,

                        language            TEXT,

                        retweet_count       INT,
                        reply_count         INT,
                        quote_count         INT,
                        like_count          INT,
                        bookmark_count      INT,

                        view_count          BIGINT,

                        conversation_id     TEXT,

                        user_blue_verified  BOOLEAN,
                        user_location       TEXT,
                        user_description    TEXT,

                        profile_image_url   TEXT,
                        cover_picture_url   TEXT,

                        media               TEXT[],

                        -- full text index column
                        text_tsv tsvector GENERATED ALWAYS AS (
                            to_tsvector('english', coalesce(text, ''))
                        ) STORED
                    ) PARTITION BY RANGE (created_at);
                """))
                
                # Create indexes
                await conn.execute(text("""
                    DO $$
                        DECLARE
                            start_date date := DATE '2016-01-01';
                            end_date   date := date_trunc('month', now()) + interval '1 month';
                            d          date;
                            part_name  text;
                        BEGIN
                            d := start_date;

                            WHILE d < end_date LOOP
                                part_name := 'tweets_' || to_char(d, 'YYYY_MM');

                                EXECUTE format(
                                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF tweets
                                    FOR VALUES FROM (%L) TO (%L);',
                                    part_name,
                                    d,
                                    d + interval '1 month'
                                );

                                -- 🔥 Uniqueness per partition
                                EXECUTE format(
                                    'CREATE UNIQUE INDEX IF NOT EXISTS %I_tweet_uidx
                                    ON %I (tweet_id);',
                                    part_name, part_name
                                );

                                -- Full-text
                                EXECUTE format(
                                    'CREATE INDEX IF NOT EXISTS %I_fts_idx
                                    ON %I USING GIN (text_tsv);',
                                    part_name, part_name
                                );

                                -- Time index
                                EXECUTE format(
                                    'CREATE INDEX IF NOT EXISTS %I_time_idx
                                    ON %I (created_at);',
                                    part_name, part_name
                                );

                                d := d + interval '1 month';
                            END LOOP;
                        END $$;
                """))
                
                await conn.commit()
                logger.info("✓ Online database initialized successfully")
        finally:
            await engine.dispose()
    
    async def get_table_count(self, db_config: dict, table_name: str = "tweets") -> int:
        """Get total count of records in a table"""
        try:
            conn = await asyncpg.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['name']
            )
            
            try:
                result = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                return result or 0
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting count from {db_config['name']}: {e}")
            return 0
    
    async def migrate_database(self, local_db_config: dict, online_db_config: dict) -> tuple[int, int]:
        """Migrate data from one local database to online database"""
        db_name = local_db_config['name']
        logger.info(f"Starting migration from {db_name}...")
        
        # Get total count for progress tracking
        total_count = await self.get_table_count(local_db_config)
        if total_count == 0:
            logger.info(f"No data found in {db_name}")
            return 0, 0
        
        logger.info(f"Found {total_count:,} tweets in {db_name}")
        
        # Connect to both databases
        local_conn = await asyncpg.connect(
            host=local_db_config['host'],
            port=local_db_config['port'],
            user=local_db_config['user'],
            password=local_db_config['password'],
            database=local_db_config['name']
        )
        
        online_conn = await asyncpg.connect(
            host=online_db_config['host'],
            port=online_db_config['port'],
            user=online_db_config['user'],
            password=online_db_config['password'],
            database=online_db_config['name']
        )
        
        migrated_count = 0
        skipped_count = 0
        
        try:
            # Process data in batches
            offset = 0
            
            while offset < total_count:
                # Fetch batch from local database
                rows = await local_conn.fetch("""
                    SELECT tweet_id, user_id, username, display_name, text, created_at, tweet_url,
                           hashtags, followers_count, following_count, verified,
                           language, retweet_count, reply_count, quote_count, like_count,
                           bookmark_count, view_count, conversation_id, user_blue_verified,
                           user_location, user_description, profile_image_url, cover_picture_url, media
                    FROM tweets
                    ORDER BY created_at
                    LIMIT $1 OFFSET $2
                """, self.batch_size, offset)
                
                if not rows:
                    break
                
                # Insert batch into online database
                try:
                    await online_conn.executemany("""
                        INSERT INTO tweets (
                            tweet_id, user_id, username, display_name, text, created_at, tweet_url,
                            hashtags, followers_count, following_count, verified,
                            language, retweet_count, reply_count, quote_count, like_count,
                            bookmark_count, view_count, conversation_id, user_blue_verified,
                            user_location, user_description, profile_image_url, cover_picture_url, media
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                            $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
                        )
                        ON CONFLICT DO NOTHING
                    """, [
                        (
                            row['tweet_id'], row['user_id'], row['username'], row['display_name'],
                            row['text'], row['created_at'], row['tweet_url'], row['hashtags'],
                            row['followers_count'], row['following_count'], row['verified'],
                            row['language'], row['retweet_count'], row['reply_count'], row['quote_count'],
                            row['like_count'], row['bookmark_count'], row['view_count'], row['conversation_id'],
                            row['user_blue_verified'], row['user_location'], row['user_description'],
                            row['profile_image_url'], row['cover_picture_url'], row['media']
                        )
                        for row in rows
                    ])
                    
                    batch_migrated = len(rows)
                    migrated_count += batch_migrated
                    
                except Exception as e:
                    logger.error(f"Error inserting batch at offset {offset}: {e}")
                    skipped_count += len(rows)
                
                offset += self.batch_size
                
                # Progress update
                progress = (offset / total_count) * 100
                logger.info(f"Progress: {progress:.1f}% ({migrated_count:,}/{total_count:,} migrated)")
        
        finally:
            await local_conn.close()
            await online_conn.close()
        
        logger.info(f"✓ Migration completed for {db_name}: {migrated_count:,} migrated, {skipped_count:,} skipped")
        return migrated_count, skipped_count
    
    async def migrate_all_databases(self) -> Dict[str, tuple[int, int]]:
        """Migrate all local databases to online database"""
        logger.info("Starting full migration process...")
        
        # Validate online database config
        if not self.online_database:
            logger.error("Online database configuration not found in migration.json")
            return {}
        
        # Test online database connection
        if not await self.test_connection(self.online_database):
            logger.error("Cannot connect to online database. Aborting migration.")
            return {}
        
        # Initialize online database
        await self.initialize_online_database(self.online_database)
        
        # Test all local database connections
        valid_databases = []
        for db_config in self.local_databases:
            if await self.test_connection(db_config):
                valid_databases.append(db_config)
        
        if not valid_databases:
            logger.error("No valid local databases found. Aborting migration.")
            return {}
        
        logger.info(f"Found {len(valid_databases)} valid local databases")
        
        # Migrate each database
        results = {}
        total_migrated = 0
        total_skipped = 0
        
        for db_config in valid_databases:
            try:
                migrated, skipped = await self.migrate_database(db_config, self.online_database)
                results[db_config['name']] = (migrated, skipped)
                total_migrated += migrated
                total_skipped += skipped
            except Exception as e:
                logger.error(f"Failed to migrate {db_config['name']}: {e}")
                results[db_config['name']] = (0, 0)
        
        # Final summary
        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        for db_name, (migrated, skipped) in results.items():
            logger.info(f"{db_name}: {migrated:,} migrated, {skipped:,} skipped")
        logger.info("-" * 60)
        logger.info(f"TOTAL: {total_migrated:,} migrated, {total_skipped:,} skipped")
        logger.info("=" * 60)
        
        return results


async def main():
    """Main function to handle command line arguments and run migration"""
    parser = argparse.ArgumentParser(description='Migrate local databases to online database')
    parser.add_argument('--config', default='migration.json', help='Migration config file path (default: migration.json)')
    parser.add_argument('--batch-size', type=int, help='Override batch size from config')
    parser.add_argument('--dry-run', action='store_true', help='Test connections without migrating data')
    
    args = parser.parse_args()
    
    # Create migrator
    migrator = DatabaseMigrator(args.config)
    
    # Override batch size if provided
    if args.batch_size:
        migrator.batch_size = args.batch_size
    
    if args.dry_run:
        logger.info("DRY RUN MODE - Testing connections only")
        
        # Test online connection
        logger.info("Testing online database connection...")
        await migrator.test_connection(migrator.online_database)
        
        # Test local connections
        logger.info("Testing local database connections...")
        for db_config in migrator.local_databases:
            await migrator.test_connection(db_config)
        
        logger.info("Dry run completed")
    else:
        # Run full migration
        start_time = datetime.now()
        results = await migrator.migrate_all_databases()
        end_time = datetime.now()
        
        duration = end_time - start_time
        logger.info(f"Migration completed in {duration}")


if __name__ == "__main__":
    asyncio.run(main())