# Date Format Handling

## Twitter Date Format

The API uses Twitter's native date format for `created_at` field:

**Format:** `Mon Jan 19 21:23:43 +0000 2026`

**Structure:** `EEE MMM dd HH:mm:ss Z yyyy`

- `EEE`: Day of week (Mon, Tue, Wed, etc.)
- `MMM`: Month (Jan, Feb, Mar, etc.)
- `dd`: Day of month (01-31)
- `HH:mm:ss`: Time in 24-hour format
- `Z`: Timezone offset (+0000 for UTC)
- `yyyy`: Year (4 digits)

## Internal Handling

### Input (Client → Server)
```python
# Client sends Twitter format
created_at = "Mon Jan 19 21:23:43 +0000 2026"

# Server parses to datetime for database storage
dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
# Result: datetime object(2026, 1, 19, 21, 23, 43, tzinfo=datetime.timezone.utc)
```

### Storage (PostgreSQL)
```sql
-- Stored as TIMESTAMP type
created_at TIMESTAMP
-- Example value: 2026-01-19 21:23:43+00
```

### Output (Server → Client)
```python
# Server retrieves datetime from database
dt = datetime(2026, 1, 19, 21, 23, 43, tzinfo=datetime.timezone.utc)

# Formats back to Twitter format
created_at_str = dt.strftime("%a %b %d %H:%M:%S %z %Y")
# Result: "Mon Jan 19 21:23:43 +0000 2026"
```

## Examples

### Valid Input Formats
```
Mon Jan 19 21:23:43 +0000 2026
Tue Feb 15 14:30:00 +0000 2026
Wed Dec 31 23:59:59 +0000 2026
```

### API Request Example
```json
{
  "tweet_id": "1234567890",
  "username": "twitter_user",
  "text": "Hello World!",
  "created_at": "Mon Jan 19 21:23:43 +0000 2026",
  "tweet_url": "https://twitter.com/user/status/1234567890",
  "hashtags": ["hello", "world"],
  "user_id": "987654321",
  "display_name": "Twitter User",
  "followers_count": 1000,
  "following_count": 500,
  "verified": true
}
```

### API Response Example
```json
{
  "keyword": "hello",
  "count": 1,
  "tweets": [
    {
      "tweet_id": "1234567890",
      "username": "twitter_user",
      "text": "Hello World!",
      "created_at": "Mon Jan 19 21:23:43 +0000 2026",
      "tweet_url": "https://twitter.com/user/status/1234567890",
      "hashtags": ["hello", "world"],
      "user_id": "987654321",
      "display_name": "Twitter User",
      "followers_count": 1000,
      "following_count": 500,
      "verified": true
    }
  ]
}
```

## Conversion Reference

| Format | Example | Usage |
|--------|---------|-------|
| Twitter String | `Mon Jan 19 21:23:43 +0000 2026` | Client ↔ Server |
| ISO 8601 | `2026-01-19T21:23:43+00:00` | Not used |
| Unix Timestamp | `1737308623` | Not used |
| Database TIMESTAMP | `2026-01-19 21:23:43+00` | Internal storage |

## Error Handling

If an invalid date format is provided, the server will return:
```json
{
  "detail": "Invalid date format. Expected: 'Mon Jan 19 21:23:43 +0000 2026'"
}
```

## Notes

- The date format must exactly match Twitter's format
- Timezone information is required (usually +0000 for UTC)
- Day and month abbreviations must be in English
- The year is always 4 digits at the end
- Time is always in 24-hour format with leading zeros
