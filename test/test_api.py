"""
Test script for the Twitter Data API
Run this after starting the server to test all endpoints
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test health check endpoint"""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_receive_data():
    """Test data receive endpoint"""
    print("\n=== Testing Data Receive ===")

    tweet_data = [
        {
            "tweetId": "1234567890",
            "username": "test_user",
            "text": "This is a test tweet about API testing #test #api",
            "createdAt": "Mon Jan 19 21:23:43 +0000 2026",
            "tweetUrl": "https://twitter.com/test_user/status/1234567890",
            "hashtags": ["test", "api"],
            "userId": "987654321",
            "displayName": "Test User",
            "followersCount": 1000,
            "followingCount": 500,
            "verified": True
        },
        {
            "tweetId": "1234567891",
            "username": "another_user",
            "text": "Another test tweet for batch insertion",
            "createdAt": "Mon Jan 19 21:25:43 +0000 2026",
            "tweetUrl": "https://twitter.com/another_user/status/1234567891",
            "hashtags": ["batch"],
            "userId": "987654322",
            "displayName": "Another User",
            "followersCount": 500,
            "followingCount": 200,
            "verified": False
        }
    ]

    response = requests.post(
        f"{BASE_URL}/api/data/receive",
        json=tweet_data
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_search():
    """Test keyword search endpoint"""
    print("\n=== Testing Keyword Search ===")

    params = {
        "keyword": "test",
        "limit": 10
    }

    response = requests.get(
        f"{BASE_URL}/api/search",
        params=params
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_cookie_save():
    """Test cookie save endpoint"""
    print("\n=== Testing Cookie Save ===")

    cookie_data = {
        "username": "test_user",
        "ct0": "test_encrypted_ct0_token_here",
        "auth_token": "test_encrypted_auth_token_here"
    }

    response = requests.post(
        f"{BASE_URL}/api/cookie/save",
        json=cookie_data
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_cookie_get():
    """Test cookie retrieval endpoint"""
    print("\n=== Testing Cookie Get ===")

    response = requests.get(f"{BASE_URL}/api/cookie/get/test_user")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_cookie_list():
    """Test cookie list endpoint"""
    print("\n=== Testing Cookie List ===")

    response = requests.get(f"{BASE_URL}/api/cookie/list")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_cookie_delete():
    """Test cookie deletion endpoint"""
    print("\n=== Testing Cookie Delete ===")

    response = requests.delete(f"{BASE_URL}/api/cookie/delete/test_user")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    print("Testing Twitter Data API")
    print("=" * 50)

    try:
        # Run all tests
        test_health_check()
        test_receive_data()
        test_search()
        test_cookie_save()
        test_cookie_get()
        test_cookie_list()
        test_cookie_delete()

        print("\n" + "=" * 50)
        print("All tests completed!")

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server.")
        print("Make sure the server is running at http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")
