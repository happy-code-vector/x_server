# Twitter Data Backend Server

A FastAPI-based server for storing and searching Twitter data with multi-database support and cookie management.

## Features

1. **Data Receive Endpoint**
   - Receives tweet data and stores it in PostgreSQL
   - Automatic database size detection and switching
   - Supports multiple database servers with automatic failover
   - Full-text search indexing

2. **Keyword Search**
   - Parallel full-text search across all databases
   - Merged and deduplicated results
   - Fast ranking and sorting

3. **Cookie Management**
   - Secure cookie storage with encryption
   - Save and retrieve encrypted Twitter cookies
   - Per-user cookie files

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```

4. Generate encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Update `.env` with your encryption key and database credentials

6. Update `config.json` with your database configurations

## Database Setup

Create PostgreSQL databases:
```sql
CREATE DATABASE twitter_data_1;
CREATE DATABASE twitter_data_2;
CREATE DATABASE twitter_data_3;
```

The server will automatically create the required tables and indexes on startup.

## Running the Server

```bash
python main.py
```

The server will start on `http://localhost:8000`

## API Endpoints

### POST /api/data/receive
Receive and store tweet data (accepts array of tweets)

**Request Body:**
```json
[
  {
    "tweet_id": "1234567890",
    "username": "twitter_user",
    "text": "This is a tweet",
    "created_at": "Mon Jan 19 21:23:43 +0000 2026",
    "tweet_url": "https://twitter.com/user/status/1234567890",
    "hashtags": ["example", "tweet"],
    "user_id": "987654321",
    "display_name": "Twitter User",
    "followers_count": 1000,
    "following_count": 500,
    "verified": true
  },
  {
    "tweet_id": "1234567891",
    "username": "another_user",
    "text": "Another tweet",
    "created_at": "Mon Jan 19 21:25:43 +0000 2026",
    "tweet_url": "https://twitter.com/another_user/status/1234567891",
    "hashtags": ["test"],
    "user_id": "987654322",
    "display_name": "Another User",
    "followers_count": 500,
    "following_count": 200,
    "verified": false
  }
]
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully inserted 2 tweets, 0 failed",
  "current_database": "twitter_data_1",
  "database_size_mb": 123.45
}
```

### GET /api/search?keyword={keyword}&limit={limit}
Search tweets by keyword across all databases

**Parameters:**
- `keyword` (required): Search keyword
- `limit` (optional): Maximum results (default: 100, max: 1000)

**Response:**
```json
{
  "keyword": "example",
  "count": 50,
  "tweets": [
    {
      "tweet_id": "1234567890",
      "username": "twitter_user",
      "text": "This is an example tweet",
      "created_at": "Mon Jan 19 21:23:43 +0000 2026",
      "tweet_url": "https://twitter.com/user/status/1234567890",
      "hashtags": ["example", "tweet"],
      "user_id": "987654321",
      "display_name": "Twitter User",
      "followers_count": 1000,
      "following_count": 500,
      "verified": true
    }
  ]
}
```

### POST /api/cookie/save
Save encrypted cookie data for a user

**Note:** The `ct0` and `auth_token` values should be **already encrypted** by the client before sending. The server stores them as-is without additional encryption.

**Request Body:**
```json
{
  "username": "twitter_user",
  "ct0": "encrypted_csrf_token",
  "auth_token": "encrypted_auth_token"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Cookie saved successfully for twitter_user"
}
```

**Stored file format** (`cookies/twitter_user.json`):
```json
{
  "ct0": "encrypted_csrf_token",
  "auth_token": "encrypted_auth_token"
}
```

### GET /api/cookie/get/{username}
Retrieve encrypted cookie data for a user

**Response:**
```json
{
  "username": "twitter_user",
  "encrypted_data": "{\"ct0\": \"encrypted_csrf_token\", \"auth_token\": \"encrypted_auth_token\"}",
  "error": null
}
```

**Note:** Returns a JSON string containing the encrypted `ct0` and `auth_token` values. The client is responsible for decrypting individual values.

### DELETE /api/cookie/delete/{username}
Delete cookie data for a user

**Response:**
```json
{
  "success": true,
  "message": "Cookie deleted successfully for twitter_user"
}
```

### GET /api/cookie/list
List all usernames with stored cookies

**Response:**
```json
{
  "success": true,
  "count": 5,
  "usernames": ["user1", "user2", "user3", "user4", "user5"]
}
```

## Configuration

### Environment Variables (.env)
- `ENCRYPTION_KEY`: Fernet encryption key for cookie encryption
- `DB_SIZE_LIMIT_MB`: Database size limit in MB (default: 1000)
- `SERVER_HOST`: Server host (default: 0.0.0.0)
- `SERVER_PORT`: Server port (default: 8000)
- Database credentials for current and next databases

### Database Configuration (config.json)
Configure multiple database servers for automatic failover:
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

## Architecture

### Database Manager
- Handles multiple database connections
- Automatic size monitoring and switching
- Parallel search across all databases
- Automatic table and index creation

### Cookie Manager
- Stores client-encrypted cookie values (ct0 and auth_token)
- File-based storage (cookies/{username}.json)
- No additional encryption applied - stores encrypted values as-is
- Returns encrypted data in JSON format for client-side decryption

### FastAPI Server
- Async/await for high performance
- CORS middleware enabled
- Pydantic models for validation
- Automatic API documentation (Swagger UI at /docs)

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Security Notes

1. Always use HTTPS in production
2. Keep encryption keys secure
3. Configure CORS appropriately
4. Use strong database passwords
5. Implement rate limiting for production
6. Consider adding authentication for API endpoints
