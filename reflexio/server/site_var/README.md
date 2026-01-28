# /user_profiler/reflexio/server/site_var
Description: Global configuration manager for site-wide variables

## Main Entry Points

- **Manager**: `site_var_manager.py` - `SiteVarManager` (singleton)
- **Sources**: `site_var_sources/` - JSON/TXT config files

## Purpose

1. **Global settings** - Model names, embedding models, feature flags
2. **Dual storage** - File-based with optional Redis caching
3. **Auto-fallback** - Redis → File system graceful degradation

## Usage

```python
from reflexio.server.site_var.site_var_manager import SiteVarManager

manager = SiteVarManager()
config = manager.get_site_var("app_config")  # Returns dict or string
```

## File Structure

```
site_var_sources/
├── app_config.json    # JSON → parsed dict
├── model_config.json
└── feature_flags.txt  # TXT → string
```

## Architecture Pattern

- **JSON priority**: `.json` files take precedence over `.txt`
- **Variable name**: Filename without extension
- **Redis optional**: Enable via `SiteVarManager(enable_redis=True)`
