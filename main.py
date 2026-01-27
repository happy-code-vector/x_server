from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import List, Optional, Union
import uvicorn
import os
from dotenv import load_dotenv

from database_manager import DatabaseManager
from cookie_manager import CookieManager
from logger import logger

load_dotenv()


# Pydantic models for request/response
class TweetData(BaseModel):
    tweetId: str = Field(..., description="Unique tweet identifier")
    username: str = Field(..., description="Twitter username")
    text: str = Field(..., description="Tweet text content")
    createdAt: str = Field(..., description="Creation timestamp (Twitter format: Mon Jan 19 21:23:43 +0000 2026)")
    tweetUrl: str = Field(..., description="URL to the tweet")
    hashtags: List[str] = Field(default_factory=list, description="List of hashtags")
    userId: str = Field(..., description="User ID")
    displayName: str = Field(..., description="Display name")
    followersCount: int = Field(..., description="Number of followers")
    followingCount: int = Field(..., description="Number of following")
    verified: bool = Field(..., description="Verification status")
    language: Optional[str] = Field(None, description="Tweet language code")
    retweetCount: Optional[int] = Field(0, description="Number of retweets")
    replyCount: Optional[int] = Field(0, description="Number of replies")
    quoteCount: Optional[int] = Field(0, description="Number of quotes")
    likeCount: Optional[int] = Field(0, description="Number of likes")
    bookmarkCount: Optional[int] = Field(0, description="Number of bookmarks")
    viewCount: Optional[str] = Field(None, description="Number of views (can be string or number)")
    conversationId: Optional[str] = Field(None, description="Conversation ID")
    userBlueVerified: Optional[bool] = Field(False, description="User blue verification status")
    userLocation: Optional[str] = Field(None, description="User location")
    userDescription: Optional[str] = Field(None, description="User description")
    profileImageUrl: Optional[str] = Field(None, description="Profile image URL")
    coverPictureUrl: Optional[str] = Field(None, description="Cover picture URL")
    media: List[str] = Field(default_factory=list, description="List of media URLs")

    @field_validator('viewCount', mode='before')
    @classmethod
    def validate_view_count(cls, v):
        """Handle viewCount that can be string, int, or None"""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return str(int(v))
        return str(v)


class TweetResponse(BaseModel):
    tweetId: str
    username: str
    text: str
    createdAt: str
    tweetUrl: str
    hashtags: List[str]
    userId: str
    displayName: str
    followersCount: int
    followingCount: int
    verified: bool
    language: Optional[str] = None
    retweetCount: int = 0
    replyCount: int = 0
    quoteCount: int = 0
    likeCount: int = 0
    bookmarkCount: int = 0
    viewCount: Optional[str] = None
    conversationId: Optional[str] = None
    userBlueVerified: bool = False
    userLocation: Optional[str] = None
    userDescription: Optional[str] = None
    profileImageUrl: Optional[str] = None
    coverPictureUrl: Optional[str] = None
    media: List[str] = []


class CookieSaveRequest(BaseModel):
    username: str = Field(..., description="Twitter username")
    ct0: str = Field(..., description="CSRF token (encrypted)")
    auth_token: str = Field(..., description="Authentication token (encrypted)")


class CookieResponse(BaseModel):
    username: str
    encrypted_data: Optional[str] = None
    error: Optional[str] = None


class SearchResponse(BaseModel):
    keyword: str
    count: int
    tweets: List[TweetResponse]


class DataReceiveResponse(BaseModel):
    success: bool
    message: str
    current_database: str
    database_size_mb: Optional[float] = None


# Initialize FastAPI app
app = FastAPI(
    title="Twitter Data API",
    description="API for storing and searching Twitter data with multi-database support",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
db_manager = DatabaseManager()
cookie_manager = CookieManager()


@app.on_event("startup")
async def startup_event():
    """Initialize databases on startup"""
    logger.info("Starting server and initializing databases...")
    await db_manager.initialize_all_databases()
    logger.info(f"Server started with {len(db_manager.databases)} databases configured")


# Add exception handler for validation errors
@app.exception_handler(Exception)
async def global_exception_handler(_, exc):
    """Global exception handler to catch and log all errors"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/data/receive", response_model=DataReceiveResponse)
async def receive_data(tweets: List[TweetData]):
    """
    Receive and store tweet data (array of tweets)

    - Accepts an array of tweets for batch insertion
    - Automatically detects database size and switches to new database if limit exceeded
    - Stores tweets in PostgreSQL with full-text search indexing
    - Supports multiple database servers with automatic failover
    - Returns success with count of inserted tweets and current database info
    """
    try:
        if not tweets:
            logger.warning("Received empty tweet array")
            return DataReceiveResponse(
                success=True,
                message="No tweets provided",
                current_database="",
                database_size_mb=0
            )

        logger.info(f"Received {len(tweets)} tweets for insertion")

        # Get current database info once for all tweets
        current_db = await db_manager.get_current_database()

        # Prepare all tweets for batch insertion (map camelCase to snake_case)
        tweet_dicts = []
        for tweet in tweets:
            tweet_dict = {
                "tweet_id": tweet.tweetId,
                "username": tweet.username,
                "text": tweet.text,
                "created_at": tweet.createdAt,  # Raw string for PostgreSQL to_timestamp
                "tweet_url": tweet.tweetUrl,
                "hashtags": tweet.hashtags,
                "user_id": tweet.userId,
                "display_name": tweet.displayName,
                "followers_count": tweet.followersCount,
                "following_count": tweet.followingCount,
                "verified": tweet.verified,
                "language": tweet.language,
                "retweet_count": tweet.retweetCount if tweet.retweetCount is not None else 0,
                "reply_count": tweet.replyCount if tweet.replyCount is not None else 0,
                "quote_count": tweet.quoteCount if tweet.quoteCount is not None else 0,
                "like_count": tweet.likeCount if tweet.likeCount is not None else 0,
                "bookmark_count": tweet.bookmarkCount if tweet.bookmarkCount is not None else 0,
                "view_count": int(tweet.viewCount) if tweet.viewCount else 0,
                "conversation_id": tweet.conversationId,
                "user_blue_verified": tweet.userBlueVerified if tweet.userBlueVerified is not None else False,
                "user_location": tweet.userLocation,
                "user_description": tweet.userDescription,
                "profile_image_url": tweet.profileImageUrl,
                "cover_picture_url": tweet.coverPictureUrl,
                "media": tweet.media
            }
            tweet_dicts.append(tweet_dict)

        # Batch insert all tweets at once
        logger.info(f"Batch inserting {len(tweet_dicts)} tweets into database: {current_db['name']}")
        inserted_count, failed_count = await db_manager.insert_tweet(tweet_dicts)

        # Get final database size
        db_size = await db_manager.check_database_size(current_db)

        logger.info(f"Successfully inserted {inserted_count}/{len(tweets)} tweets, {failed_count} failed")

        return DataReceiveResponse(
            success=True,
            message=f"Successfully inserted {inserted_count} tweets, {failed_count} failed",
            current_database=current_db['name'],
            database_size_mb=round(db_size, 2)
        )

    except Exception as e:
        logger.error(f"Error receiving tweet data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search", response_model=SearchResponse)
async def search_keyword(
    keyword: str = Query(..., description="Search keyword"),
    limit: int = Query(10000000, ge=1, le=1000, description="Maximum number of results")
):
    """
    Search tweets by keyword across all databases

    - Performs parallel full-text search across all database servers
    - Merges and deduplicates results from all databases
    - Returns results sorted by creation date (newest first)
    - Uses PostgreSQL full-text search with ranking
    """
    try:
        if not keyword or len(keyword.strip()) == 0:
            logger.warning("Empty search keyword received")
            raise HTTPException(status_code=400, detail="Keyword cannot be empty")

        logger.info(f"Searching for keyword: '{keyword}' with limit: {limit}")

        # Search across all databases in parallel
        results = await db_manager.search_all_databases(keyword, limit)

        logger.info(f"Search completed: found {len(results)} results across all databases")

        # Convert to response format (map snake_case to camelCase)
        tweets = []
        for r in results:
            # Format datetime back to Twitter format
            created_at_str = r['created_at'].strftime("%a %b %d %H:%M:%S %z %Y")

            tweets.append(TweetResponse(
                tweetId=r['tweet_id'],
                username=r['username'],
                text=r['text'],
                createdAt=created_at_str,
                tweetUrl=r['tweet_url'],
                hashtags=r.get('hashtags', []),
                userId=r['user_id'],
                displayName=r['display_name'],
                followersCount=r['followers_count'],
                followingCount=r['following_count'],
                verified=r['verified'],
                language=r.get('language'),
                retweetCount=r.get('retweet_count', 0),
                replyCount=r.get('reply_count', 0),
                quoteCount=r.get('quote_count', 0),
                likeCount=r.get('like_count', 0),
                bookmarkCount=r.get('bookmark_count', 0),
                viewCount=str(r.get('view_count', 0)),
                conversationId=r.get('conversation_id'),
                userBlueVerified=r.get('user_blue_verified', False),
                userLocation=r.get('user_location'),
                userDescription=r.get('user_description'),
                profileImageUrl=r.get('profile_image_url'),
                coverPictureUrl=r.get('cover_picture_url'),
                media=r.get('media', [])
            ))

        logger.info(f"Returning {len(tweets)} unique tweets to client")

        return SearchResponse(
            keyword=keyword,
            count=len(tweets),
            tweets=tweets
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during search for keyword '{keyword}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/api/cookie/save")
async def save_cookie(request: CookieSaveRequest):
    """
    Save encrypted cookie data for a user

    - Expects ct0 and auth_token to be already encrypted by the client
    - Stores the encrypted values directly to username.json file
    - No additional encryption is applied (data is already encrypted)
    - Returns the encrypted data when retrieved via /api/cookie/get/{username}
    """
    try:
        logger.info(f"Received cookie save request for user: {request.username}")
        success = cookie_manager.save_cookie(
            username=request.username,
            ct0=request.ct0,
            auth_token=request.auth_token
        )

        if success:
            logger.info(f"Cookie save API response: success for {request.username}")
            return {
                "success": True,
                "message": f"Cookie saved successfully for {request.username}"
            }
        else:
            logger.error(f"Cookie save API failed for {request.username}")
            raise HTTPException(status_code=500, detail="Failed to save cookie")

    except Exception as e:
        logger.error(f"Cookie save API error for {request.username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save cookie: {str(e)}")


@app.get("/api/cookie/get/{username}", response_model=CookieResponse)
async def get_cookie(username: str):
    """
    Retrieve encrypted cookie data for a user

    - Returns JSON string containing encrypted ct0 and auth_token values
    - The values are stored exactly as they were received (already encrypted)
    - Client is responsible for decryption of individual values
    - Returns null if user not found
    """
    try:
        logger.info(f"Received cookie get request for user: {username}")
        encrypted_data = cookie_manager.get_cookie(username)

        if encrypted_data is None:
            logger.warning(f"Cookie get API: no data found for {username}")
            return CookieResponse(
                username=username,
                encrypted_data=None,
                error=f"No cookie found for user: {username}"
            )

        logger.info(f"Cookie get API: returning data for {username}")
        return CookieResponse(
            username=username,
            encrypted_data=encrypted_data
        )

    except Exception as e:
        logger.error(f"Cookie get API error for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cookie: {str(e)}")


@app.delete("/api/cookie/delete/{username}")
async def delete_cookie(username: str):
    """
    Delete cookie data for a user
    """
    try:
        logger.info(f"Received cookie delete request for user: {username}")
        success = cookie_manager.delete_cookie(username)

        if success:
            logger.info(f"Cookie delete API: successfully deleted {username}")
            return {
                "success": True,
                "message": f"Cookie deleted successfully for {username}"
            }
        else:
            logger.warning(f"Cookie delete API: no cookie found for {username}")
            raise HTTPException(status_code=404, detail=f"No cookie found for user: {username}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cookie delete API error for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete cookie: {str(e)}")


@app.get("/api/cookie/list")
async def list_cookies():
    """
    List all usernames with stored cookies
    """
    try:
        logger.info("Received cookie list request")
        usernames = cookie_manager.list_cookies()
        logger.info(f"Cookie list API: returning {len(usernames)} users")
        return {
            "success": True,
            "count": len(usernames),
            "usernames": usernames
        }
    except Exception as e:
        logger.error(f"Cookie list API error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list cookies: {str(e)}")


@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "name": "Twitter Data API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/data/receive": "Receive and store tweet data (array of tweets)",
            "GET /api/search": "Search tweets by keyword",
            "POST /api/cookie/save": "Save encrypted cookie data",
            "GET /api/cookie/get/{username}": "Retrieve encrypted cookie data",
            "DELETE /api/cookie/delete/{username}": "Delete cookie data",
            "GET /api/cookie/list": "List all stored usernames"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint with comprehensive database status
    """
    try:
        current_db = await db_manager.get_current_database()
        
        # Get database size in GB
        size_mb = await db_manager.check_database_size(current_db)
        size_gb = round(size_mb / 1024, 2)
        
        # Get tweet count from current database
        tweet_count = await db_manager.get_table_count(current_db, "tweets")
        
        return {
            "status": "healthy",
            "databases": {
                "total_count": len(db_manager.databases),
                "current_database": current_db['name'],
                "current_database_index": db_manager.current_db_index,
                "size_limit_mb": db_manager.db_size_limit_mb
            },
            "current_database_stats": {
                "name": current_db['name'],
                "tweet_count": tweet_count,
                "size_gb": size_gb,
                "size_mb": round(size_mb, 2),
                "capacity_used_percent": round((size_mb / db_manager.db_size_limit_mb) * 100, 2)
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "databases": {
                "total_count": len(db_manager.databases) if db_manager.databases else 0,
                "current_database": "unknown"
            }
        }


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=server_host,
        port=server_port,
        reload=True,
        log_level="info"
    )
