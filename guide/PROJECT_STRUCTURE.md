# Project Structure

```
backend server/
├── main.py                 # FastAPI application and API endpoints
├── database_manager.py     # Multi-database management logic
├── cookie_manager.py       # Cookie encryption and storage
├── config.json             # Database configuration
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── generate_key.py        # Script to generate encryption key
├── setup_databases.py     # Script to initialize databases
├── test_api.py            # API testing script
├── README.md              # Full documentation
├── QUICKSTART.md          # Quick start guide
├── .gitignore             # Git ignore rules
└── cookies/               # Directory for encrypted cookie files (created at runtime)
    └── {username}.json    # Individual cookie files
```

## Core Components

### 1. main.py
FastAPI application with the following endpoints:
- `POST /api/data/receive` - Receive and store tweet data
- `GET /api/search` - Search tweets by keyword
- `POST /api/cookie/save` - Save encrypted cookies
- `GET /api/cookie/get/{username}` - Retrieve encrypted cookies
- `DELETE /api/cookie/delete/{username}` - Delete cookies
- `GET /api/cookie/list` - List all stored usernames
- `GET /health` - Health check

### 2. database_manager.py
Handles all database operations:
- Multi-database connection management
- Automatic size monitoring and switching
- Parallel full-text search across all databases
- Table and index initialization

Key methods:
- `initialize_database()` - Create tables and indexes
- `check_database_size()` - Monitor database size
- `get_current_database()` - Get active database with auto-switching
- `insert_tweet()` - Insert tweet data
- `search_all_databases()` - Parallel search across all databases

### 3. cookie_manager.py
Manages cookie encryption and storage:
- Fernet symmetric encryption
- File-based storage in `cookies/` directory
- Per-user cookie files

Key methods:
- `save_cookie()` - Encrypt and save cookie data
- `get_cookie()` - Retrieve encrypted cookie
- `decrypt_cookie()` - Decrypt cookie data
- `delete_cookie()` - Remove cookie file
- `list_cookies()` - List all stored usernames

## Database Schema

### tweets table
```sql
CREATE TABLE tweets (
    tweet_id TEXT PRIMARY KEY,
    username TEXT,
    text TEXT,
    created_at TIMESTAMP,
    tweet_url TEXT,
    hashtags TEXT[],
    user_id TEXT,
    display_name TEXT,
    followers_count INT,
    following_count INT,
    verified BOOLEAN
);
```

### Indexes
- Full-text search index on `text` column using GIN
- B-tree index on `username` for faster filtering
- B-tree index on `created_at` for sorting

## Configuration Files

### config.json
Stores database connection information:
```json
{
  "databases": [
    {
      "id": 1,
      "host": "localhost",
      "port": 5432,
      "name": "twitter_data_1",
      "user": "postgres",
      "password": "your-password",
      "is_active": true
    }
  ],
  "current_db_index": 0,
  "db_size_limit_mb": 1000
}
```

### .env
Environment variables:
- `ENCRYPTION_KEY` - Fernet key for cookie encryption
- `DB_SIZE_LIMIT_MB` - Database size limit in MB
- `SERVER_HOST` - Server host address
- `SERVER_PORT` - Server port
- Database credentials for current and next databases

## Data Flow

### Receiving Tweet Data
1. Client POSTs tweet data to `/api/data/receive`
2. Server validates data using Pydantic models
3. DatabaseManager checks current database size
4. If size exceeds limit, switches to next database
5. Inserts tweet into active database
6. Returns success with current database info

### Searching Tweets
1. Client GETs `/api/search?keyword={keyword}`
2. Server validates keyword parameter
3. DatabaseManager searches all databases in parallel using asyncio
4. Results from all databases are merged and deduplicated
5. Results sorted by creation date (newest first)
6. Returns merged results

### Saving Cookies
1. Client POSTs to `/api/cookie/save` with encrypted data
2. CookieManager encrypts data using Fernet
3. Saves encrypted data to `cookies/{username}.json`
4. Returns success confirmation

### Retrieving Cookies
1. Client GETs `/api/cookie/get/{username}`
2. CookieManager reads encrypted file
3. Returns encrypted data (client handles decryption)

## Security Features

1. **Cookie Encryption**: All cookies are encrypted using Fernet symmetric encryption
2. **Environment Variables**: Sensitive data stored in `.env` file
3. **SQL Injection Prevention**: Using parameterized queries
4. **CORS Configuration**: Configurable CORS middleware
5. **Input Validation**: Pydantic models for request validation

## Performance Features

1. **Async/Await**: Full async support for high performance
2. **Parallel Search**: All databases searched simultaneously
3. **Connection Pooling**: Efficient database connection management
4. **Full-Text Search**: PostgreSQL GIN indexes for fast text search
5. **Automatic Failover**: Seamless switching between databases

## Extension Points

1. **Add Authentication**: Integrate JWT or OAuth2
2. **Rate Limiting**: Add rate limiting middleware
3. **Caching**: Implement Redis for frequently accessed data
4. **Logging**: Add structured logging
5. **Monitoring**: Integrate Prometheus or similar
6. **Background Tasks**: Add scheduled tasks using Celery
