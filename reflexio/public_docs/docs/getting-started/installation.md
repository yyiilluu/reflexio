# Installation

## Requirements

- Python 3.7+
- pip

## Install

```bash
pip install reflexio-client
```

For development or if using Poetry:

```bash
poetry add reflexio-client
```

## Verify Installation

Check the installed version:

```python
import reflexio
print(reflexio.__version__)
```

Initialize the client:

```python
from reflexio import ReflexioClient

client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")
print("Reflexio client initialized successfully")
```

## Authentication

After installation, authenticate using one of two methods:

```python
# Option 1: Login with email/password (API key is automatically set)
token = client.login("user@example.com", "password")
# token.api_key contains your API key - save it for future use (it never expires)

# Option 2: Initialize with a previously saved API key (more efficient - skips login)
client = ReflexioClient(
    api_key=token.api_key,  # Use the saved token.api_key from a previous login
    url_endpoint="http://127.0.0.1:8081/"
)
```

## Next Steps

- [Account Setup](account-setup.md) — Set up Supabase and register
- [Quick Start Guide](quickstart.md) — Learn basic usage
- [Configuration Guide](configuration.md) — Complete configuration reference
