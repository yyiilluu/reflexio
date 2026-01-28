# Authentication Examples

This page covers all aspects of authentication with Reflexio, including setup, token management, and best practices for different deployment scenarios.

## Basic Authentication

### Email/Password Login

```python
import reflexio

# Initialize client with endpoint
client = reflexio.ReflexioClient(url_endpoint="http://127.0.0.1:8081/")

# Perform login - client automatically stores the API key
token = client.login("your_email@example.com", "your_password")

print(f"Authenticated successfully!")
print(f"Token type: {token.token_type}")

# The API key never expires - save it for future use
print(f"Save this key for future sessions: {token.api_key}")
```

### Direct API Key Authentication

If you already have an API key (obtained from `token.api_key` after a previous login), you can initialize the client directly:

```python
# Initialize client with a previously saved API key (from token.api_key)
client = reflexio.ReflexioClient(
    api_key="<your_saved_token.api_key>",  # The token.api_key value from a previous login
    url_endpoint="http://127.0.0.1:8081/"
)

# No login required - ready to use immediately
response = client.get_config()
print("Client ready with direct API key authentication")
```

## Environment-Specific Configuration

### Local Development

```python
import os
import reflexio

# Local development setup
client = reflexio.ReflexioClient(
    url_endpoint="http://127.0.0.1:8081/"  # Local development server
)

# Use environment variables for credentials
email = os.getenv("REFLEXIO_EMAIL", "dev@example.com")
password = os.getenv("REFLEXIO_PASSWORD", "dev_password")

# Login automatically sets the API key on the client
token = client.login(email, password)
```

### Production Environment

```python
import os
import reflexio

# Option 1: Use saved API key (recommended for production)
# The API key never expires, so save it after first login
client = reflexio.ReflexioClient(
    api_key=os.getenv("REFLEXIO_API_KEY"),
    url_endpoint=os.getenv("REFLEXIO_ENDPOINT", "https://api.reflexio.com")
)

# Option 2: Login with credentials (API key is automatically set)
client = reflexio.ReflexioClient(
    url_endpoint=os.getenv("REFLEXIO_ENDPOINT", "https://api.reflexio.com")
)
token = client.login(
    email=os.getenv("REFLEXIO_EMAIL"),
    password=os.getenv("REFLEXIO_PASSWORD")
)
# Save token.api_key to environment/secrets for future use
```

## Advanced Authentication Patterns

### Token Persistence and Reuse

```python
import json
import os
from pathlib import Path
import reflexio

class ReflexioAuthManager:
    """Manages authentication with token persistence."""

    def __init__(self, endpoint: str, token_file: str = ".reflexio_token"):
        self.client = reflexio.ReflexioClient(url_endpoint=endpoint)
        self.token_file = Path(token_file)
        self.token = None

    def authenticate(self, email: str, password: str, save_token: bool = True):
        """Authenticate and optionally save token for reuse."""
        try:
            # Try to load existing token first
            if self.token_file.exists() and save_token:
                self._load_token()
                if self._validate_token():
                    print("✅ Using saved token")
                    return True
        except Exception:
            pass  # Fall back to fresh login

        # Perform fresh login (automatically sets client.api_key)
        print("🔑 Performing fresh login...")
        self.token = self.client.login(email, password)
        # Note: login() automatically sets client.api_key, no manual assignment needed

        # Save token for future use (API key never expires)
        if save_token:
            self._save_token()

        print("✅ Authentication successful")
        return True

    def _save_token(self):
        """Save token to file."""
        token_data = {
            "api_key": self.token.api_key,
            "token_type": self.token.token_type
        }
        with open(self.token_file, 'w') as f:
            json.dump(token_data, f)

        # Set restrictive permissions
        os.chmod(self.token_file, 0o600)

    def _load_token(self):
        """Load token from file."""
        with open(self.token_file, 'r') as f:
            token_data = json.load(f)

        # Reconstruct token object and set on client
        from reflexio_commons.api_schema.login_schema import Token
        self.token = Token(**token_data)
        self.client.api_key = self.token.api_key  # Set manually when loading from file

    def _validate_token(self) -> bool:
        """Validate that the current token works."""
        try:
            # Try a simple API call to validate token
            self.client.get_config()
            return True
        except Exception:
            return False

    def logout(self):
        """Clear token and remove saved file."""
        self.client.api_key = ""
        self.token = None

        if self.token_file.exists():
            self.token_file.unlink()

        print("🚪 Logged out successfully")

# Usage
auth_manager = ReflexioAuthManager("http://127.0.0.1:8081/")
auth_manager.authenticate("user@example.com", "password")

# Client is now ready to use
client = auth_manager.client
```
