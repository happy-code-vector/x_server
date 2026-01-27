import json
from pathlib import Path
from typing import Optional
from logger import logger


class CookieManager:
    """Manages Twitter cookie storage for encrypted data"""

    def __init__(self, storage_dir: str = "cookies"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save_cookie(self, username: str, ct0: str, auth_token: str) -> bool:
        """
        Save already-encrypted cookie data to username.json file

        Args:
            username: Twitter username
            ct0: Already-encrypted CSRF token (encrypted by client)
            auth_token: Already-encrypted authentication token (encrypted by client)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cookie_data = {
                "ct0": ct0,
                "auth_token": auth_token
            }

            # Store the already-encrypted data as JSON
            # The ct0 and auth_token are already encrypted by the client
            json_str = json.dumps(cookie_data)

            # Save to file (no additional encryption - data is already encrypted)
            file_path = self.storage_dir / f"{username}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

            logger.info(f"Cookie saved successfully for user: {username}")
            return True
        except Exception as e:
            logger.error(f"Error saving cookie for {username}: {e}")
            return False

    def get_cookie(self, username: str) -> Optional[str]:
        """
        Retrieve encrypted cookie data for username

        Args:
            username: Twitter username

        Returns:
            str: JSON string with encrypted ct0 and auth_token, or None if not found
        """
        try:
            file_path = self.storage_dir / f"{username}.json"

            if not file_path.exists():
                logger.warning(f"Cookie not found for user: {username}")
                return None

            # Read encrypted data (stored as JSON with encrypted values)
            with open(file_path, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()

            logger.info(f"Cookie retrieved successfully for user: {username}")
            # Return the JSON string with encrypted ct0 and auth_token
            return encrypted_data

        except Exception as e:
            logger.error(f"Error retrieving cookie for {username}: {e}")
            return None

    def delete_cookie(self, username: str) -> bool:
        """
        Delete cookie file for username

        Args:
            username: Twitter username

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_path = self.storage_dir / f"{username}.json"
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cookie deleted successfully for user: {username}")
                return True
            logger.warning(f"Cookie file not found for deletion: {username}")
            return False
        except Exception as e:
            logger.error(f"Error deleting cookie for {username}: {e}")
            return False

    def list_cookies(self) -> list:
        """
        List all stored usernames

        Returns:
            list: List of usernames with stored cookies
        """
        try:
            cookie_files = list(self.storage_dir.glob("*.json"))
            usernames = [f.stem for f in cookie_files]
            logger.info(f"Listed {len(usernames)} stored cookies")
            return usernames
        except Exception as e:
            logger.error(f"Error listing cookies: {e}")
            return []
