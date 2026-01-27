# Quick Start Guide

## Step 1: Install Dependencies

```bash
# Activate virtual environment (if you have one)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

## Step 2: Generate Encryption Key

```bash
python generate_key.py
```

Copy the generated key and add it to your `.env` file:
```
ENCRYPTION_KEY=your-generated-key-here
```

## Step 3: Create .env File

Copy the example file:
```bash
cp .env.example .env
```

Then edit `.env` and update:
- `ENCRYPTION_KEY` (from Step 2)
- Database credentials for all databases
- Server configuration

## Step 4: Configure Databases

Edit `config.json` with your PostgreSQL database credentials.

## Step 5: Create PostgreSQL Databases

Connect to PostgreSQL and create the databases:
```sql
CREATE DATABASE twitter_data_1;
CREATE DATABASE twitter_data_2;
CREATE DATABASE twitter_data_3;
```

## Step 6: Initialize Databases (Optional)

```bash
python setup_databases.py
```

This will create the required tables and indexes. The server will also do this automatically on startup.

## Step 7: Start the Server

```bash
python main.py
```

The server will start at `http://localhost:8000`

## Step 8: Test the API

### Health Check
```bash
curl http://localhost:8000/health
```

### Receive Tweet Data
```bash
curl -X POST http://localhost:8000/api/data/receive \
  -H "Content-Type: application/json" \
  -d '[
    {
      "tweet_id": "1234567890",
      "username": "testuser",
      "text": "This is a test tweet",
      "created_at": "Mon Jan 19 21:23:43 +0000 2026",
      "tweet_url": "https://twitter.com/testuser/status/1234567890",
      "hashtags": ["test", "tweet"],
      "user_id": "987654321",
      "display_name": "Test User",
      "followers_count": 100,
      "following_count": 50,
      "verified": false
    },
    {
      "tweet_id": "1234567891",
      "username": "anotheruser",
      "text": "Another test tweet",
      "created_at": "Mon Jan 19 21:25:43 +0000 2026",
      "tweet_url": "https://twitter.com/anotheruser/status/1234567891",
      "hashtags": ["test"],
      "user_id": "987654322",
      "display_name": "Another User",
      "followers_count": 200,
      "following_count": 100,
      "verified": true
    }
  ]'
```

### Search Tweets
```bash
curl "http://localhost:8000/api/search?keyword=test&limit=10"
```

### Save Cookie
```bash
curl -X POST http://localhost:8000/api/cookie/save \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "ct0": "encrypted_ct0_token",
    "auth_token": "encrypted_auth_token"
  }'
```

### Get Cookie
```bash
curl http://localhost:8000/api/cookie/get/testuser
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting

### Database Connection Error
- Verify PostgreSQL is running
- Check database credentials in `.env` and `config.json`
- Ensure databases exist

### Encryption Key Error
- Make sure you ran `python generate_key.py`
- Verify `ENCRYPTION_KEY` is set in `.env`

### Port Already in Use
- Change `SERVER_PORT` in `.env`
- Or kill the process using port 8000
