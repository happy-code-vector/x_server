import asyncio
import json
from typing import List, Dict, Optional
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
from pathlib import Path
from logger import logger


class DatabaseManager:
    """Manages multiple PostgreSQL databases for Twitter data storage"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.databases = self.config.get("databases", [])
        self.current_db_index = self.config.get("current_db_index", 0)
        self.db_size_limit_mb = self.config.get("db_size_limit_mb", 1000)

    def _load_config(self) -> dict:
        """Load database configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {"databases": [], "current_db_index": 0, "db_size_limit_mb": 1000}

    def _save_config(self):
        """Save current configuration to JSON file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _get_connection_string(self, db_config: dict) -> str:
        """Generate PostgreSQL connection string"""
        return f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"

    def _get_async_connection_string(self, db_config: dict) -> str:
        """Generate async PostgreSQL connection string"""
        return f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"

    async def check_database_size(self, db_config: dict) -> float:
        """Check current database size in MB"""
        conn_string = self._get_async_connection_string(db_config)
        engine = create_async_engine(conn_string, poolclass=NullPool)

        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(f"""
                        SELECT pg_database_size('{db_config['name']}') / 1024 / 1024 as size_mb
                    """)
                )
                size_mb = float(result.scalar())
                return size_mb
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

    async def get_current_database(self) -> dict:
        """Get current active database configuration"""
        current_db = self.databases[self.current_db_index]

        # Check if database size exceeds limit
        size_mb = await self.check_database_size(current_db)

        if size_mb > self.db_size_limit_mb:
            logger.warning(f"Database {current_db['name']} size {size_mb:.2f} MB exceeds limit {self.db_size_limit_mb} MB")
            # Switch to next database
            next_index = (self.current_db_index + 1) % len(self.databases)

            if next_index != self.current_db_index:
                # Mark current as inactive
                self.databases[self.current_db_index]['is_active'] = False

                # Switch to next
                self.current_db_index = next_index
                self.databases[self.current_db_index]['is_active'] = True
                self.config['current_db_index'] = self.current_db_index
                self._save_config()

                current_db = self.databases[self.current_db_index]
                logger.info(f"Switched to database: {current_db['name']} (previous size: {size_mb:.2f} MB)")
            else:
                logger.error(f"All databases ({len(self.databases)}) are full!")
        else:
            logger.debug(f"Database {current_db['name']} size: {size_mb:.2f} MB / {self.db_size_limit_mb} MB")

        return current_db

    async def initialize_database(self, db_config: dict):
        """Initialize database with required table and full-text search index"""
        conn_string = self._get_async_connection_string(db_config)
        engine = create_async_engine(conn_string, poolclass=NullPool)

        try:
            async with engine.connect() as conn:
                # Create tweets table
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tweets (
                        tweet_id TEXT PRIMARY KEY,
                        user_id TEXT,
                        username TEXT,
                        display_name TEXT,
                        text TEXT,
                        created_at TIMESTAMPTZ,
                        tweet_url TEXT,
                        hashtags TEXT[],
                        followers_count INT4,
                        following_count INT4,
                        verified BOOL,
                        text_tsv TSVECTOR,
                        language TEXT,
                        retweet_count INT4,
                        reply_count INT4,
                        quote_count INT4,
                        like_count INT4,
                        bookmark_count INT4,
                        view_count INT8,
                        conversation_id TEXT,
                        user_blue_verified BOOL,
                        user_location TEXT,
                        user_description TEXT,
                        profile_image_url TEXT,
                        cover_picture_url TEXT,
                        media TEXT[]
                    )
                """))

                # Create full-text search index using text_tsv column
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_text_search
                    ON tweets USING gin(text_tsv)
                """))

                # Create index on username for faster searches
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_username
                    ON tweets(username)
                """))

                # Create index on created_at for sorting
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_created_at
                    ON tweets(created_at DESC)
                """))

                # Create trigger function to update text_tsv automatically
                await conn.execute(text("""
                    CREATE OR REPLACE FUNCTION tweets_text_tsv_trigger() RETURNS trigger AS $$
                    BEGIN
                        NEW.text_tsv := to_tsvector('english', COALESCE(NEW.text, ''));
                        RETURN NEW;
                    END
                    $$ LANGUAGE plpgsql
                """))

                # Create trigger to call the function on INSERT and UPDATE
                await conn.execute(text("""
                    DROP TRIGGER IF EXISTS tweets_text_tsv_update ON tweets
                """))
                await conn.execute(text("""
                    CREATE TRIGGER tweets_text_tsv_update
                    BEFORE INSERT OR UPDATE ON tweets
                    FOR EACH ROW
                    EXECUTE FUNCTION tweets_text_tsv_trigger()
                """))

                await conn.commit()
                logger.info(f"Database {db_config['name']} initialized successfully")
        finally:
            await engine.dispose()

    async def insert_tweet(self, tweet_data: list) -> tuple[int, int]:
        """
        Insert tweet data into current database (batch insert)

        Args:
            tweet_data: List of tweet dictionaries

        Returns:
            tuple: (inserted_count, failed_count)
        """
        current_db = await self.get_current_database()
        inserted_count = 0
        failed_count = 0

        if not tweet_data:
            return 0, 0

        try:
            conn = await asyncpg.connect(
                host=current_db['host'],
                port=current_db['port'],
                user=current_db['user'],
                password=current_db['password'],
                database=current_db['name']
            )

            try:
                # Check how many tweets already exist before insertion
                # tweet_ids = [tweet['tweet_id'] for tweet in tweet_data]
                # existing_tweets = await conn.fetch(
                #     "SELECT tweet_id FROM tweets WHERE tweet_id = ANY($1)",
                #     tweet_ids
                # )
                # existing_ids = {row['tweet_id'] for row in existing_tweets}
                # conflict_count = len(existing_ids)

                # Use executemany for batch insertion
                # Convert camelCase JSON fields to snake_case database columns
                # text_tsv is automatically populated by the trigger
                await conn.executemany("""
                    INSERT INTO tweets (
                        tweet_id, user_id, username, display_name, text, created_at, tweet_url,
                        hashtags, followers_count, following_count, verified,
                        language, retweet_count, reply_count, quote_count, like_count,
                        bookmark_count, view_count, conversation_id, user_blue_verified,
                        user_location, user_description, profile_image_url, cover_picture_url, media
                    ) VALUES (
                        $1, $2, $3, $4, $5, to_timestamp($6, 'Dy Mon DD HH24:MI:SS TZ YYYY'), $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
                    )
                    ON CONFLICT DO NOTHING;
                """,
                    [
                        (
                            tweet.get('tweetId') or tweet.get('tweet_id'),
                            tweet.get('userId') or tweet.get('user_id'),
                            tweet.get('username'),
                            tweet.get('displayName') or tweet.get('display_name'),
                            tweet.get('text'),
                            tweet.get('createdAt') or tweet.get('created_at'),  # Already a datetime/timestamptz
                            tweet.get('tweetUrl') or tweet.get('tweet_url'),
                            tweet.get('hashtags') or [],
                            tweet.get('followersCount') or tweet.get('followers_count') or 0,
                            tweet.get('followingCount') or tweet.get('following_count') or 0,
                            tweet.get('verified') or False,
                            tweet.get('language'),
                            tweet.get('retweetCount') or tweet.get('retweet_count') or 0,
                            tweet.get('replyCount') or tweet.get('reply_count') or 0,
                            tweet.get('quoteCount') or tweet.get('quote_count') or 0,
                            tweet.get('likeCount') or tweet.get('like_count') or 0,
                            tweet.get('bookmarkCount') or tweet.get('bookmark_count') or 0,
                            tweet.get('viewCount') or tweet.get('view_count') or 0,
                            tweet.get('conversationId') or tweet.get('conversation_id'),
                            tweet.get('userBlueVerified') or tweet.get('user_blue_verified') or False,
                            tweet.get('userLocation') or tweet.get('user_location'),
                            tweet.get('userDescription') or tweet.get('user_description'),
                            tweet.get('profileImageUrl') or tweet.get('profile_image_url'),
                            tweet.get('coverPictureUrl') or tweet.get('cover_picture_url'),
                            tweet.get('media') or []
                        )
                        for tweet in tweet_data
                    ]
                )

                # inserted_count = len(tweet_data) - conflict_count
                # logger.info(f"Batch insert: {inserted_count} inserted, {conflict_count} conflicts out of {len(tweet_data)} total")
                # return inserted_count, conflict_count
                logger.info(f"Successfully batch inserted {len(tweet_data)} tweets")
                return len(tweet_data), 0
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error inserting {len(tweet_data)} tweets: {e}")
            
            with open(f"{tweet_data[0]['tweet_id']}.json", 'w', encoding='utf-8') as f:
                json.dump(tweet_data, f, indent= 2)

            return 0, len(tweet_data)

    async def search_all_databases(self, keyword: str, limit: int = 100) -> List[dict]:
        """Search keyword across all databases in parallel"""
        search_tasks = []

        for db_config in self.databases:
            search_tasks.append(self._search_single_database(db_config, keyword, limit))

        # Execute all searches in parallel
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Merge and deduplicate results
        all_tweets = []
        seen_ids = set()

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Search error: {result}")
                continue

            for tweet in result:
                if tweet['tweet_id'] not in seen_ids:
                    seen_ids.add(tweet['tweet_id'])
                    all_tweets.append(tweet)

        # Sort by created_at descending
        all_tweets.sort(key=lambda x: x['created_at'], reverse=True)

        return all_tweets[:limit]

    async def _search_single_database(self, db_config: dict, keyword: str, limit: int) -> List[dict]:
        """Search a single database for keyword"""
        conn_string = self._get_async_connection_string(db_config)

        try:
            conn = await asyncpg.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['name']
            )

            try:
                query = """
                    SELECT tweet_id, user_id, username, display_name, text, created_at, tweet_url,
                           hashtags, followers_count, following_count, verified,
                           language, retweet_count, reply_count, quote_count, like_count,
                           bookmark_count, view_count, conversation_id, user_blue_verified,
                           user_location, user_description, profile_image_url, cover_picture_url, media
                    FROM tweets
                    WHERE text_tsv @@ plainto_tsquery('english', $1)
                    ORDER BY created_at DESC
                    LIMIT $2
                """
                rows = await conn.fetch(query, keyword, limit)

                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error searching database {db_config['name']}: {e}")
            return []

    async def initialize_all_databases(self):
        """Initialize all databases with required tables"""
        for db_config in self.databases:
            try:
                await self.initialize_database(db_config)
            except Exception as e:
                logger.error(f"Error initializing database {db_config['name']}: {e}")
