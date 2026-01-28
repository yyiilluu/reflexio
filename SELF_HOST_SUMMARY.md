# Self-Host Mode - Quick Summary

## What Was Done

Successfully implemented self-host mode for the Reflexio application, allowing it to run **without authentication** and **without a database**.

## Key Changes

### 1. Database (reflexio/server/db/database.py)
- ✅ Detects `SELF_HOST=true` environment variable
- ✅ Skips database initialization completely
- ✅ Uses in-memory SQLite as fallback (never actually used)

### 2. Authentication (reflexio/server/api.py)
- ✅ All API endpoints skip authentication when `SELF_HOST=true`
- ✅ Uses default org ID: `self-host-org`
- ✅ No Bearer token required

### 3. Storage Path Fix (reflexio/server/services/configurator/local_json_config_storage.py)
- ✅ **Critical fix**: Ensures all paths are absolute
- ✅ Prevents `StorageError: non absolute path` error
- ✅ Converts relative paths using `os.path.abspath()`

### 4. Local Storage
- ✅ All data stored in: `/Users/yilu/repos/user_profiler/reflexio/data/`
- ✅ Config stored in: `reflexio/data/configs/`
- ✅ No S3, Supabase, or PostgreSQL required

## Files Modified

1. `reflexio/server/db/database.py` - Skip DB in self-host mode
2. `reflexio/server/api.py` - Skip auth in self-host mode
3. `reflexio/server/api_endpoints/publisher_api.py` - Use local storage
4. `reflexio/server/api_endpoints/retriever_api.py` - Use local storage
5. `reflexio/server/services/configurator/local_json_config_storage.py` - Fix absolute paths

## How to Use

### Start the Server
```bash
# Make sure SELF_HOST=true in .env
./start_server_local.sh
```

You should see:
```
Self-host mode enabled - skipping database initialization
```

### Test It
```bash
# No authentication needed!
curl -X POST "http://0.0.0.0:8081/api/publish_interaction" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-1",
    "user_id": "user-1",
    "interaction_requests": [{
      "content": "Test message",
      "role": "user"
    }],
    "source": "test",
    "agent_version": "v1.0"
  }'
```

Expected response:
```json
{"success": true}
```

### Check Stored Data
```bash
# Data is stored here:
ls -la reflexio/data/
```

## Toggle Self-Host Mode

### Enable Self-Host Mode
In `.env`:
```bash
SELF_HOST=true
```
Then restart server.

### Disable Self-Host Mode (Use Database + Auth)
In `.env`:
```bash
SELF_HOST=false
```
Then restart server.

## Benefits

✅ **No Database Required** - Perfect for development and single-user deployments
✅ **No Authentication** - Quick testing without tokens
✅ **Local Storage** - All data in one directory
✅ **Easy Backup** - Just copy `reflexio/data/` folder
✅ **Privacy** - Data stays on your machine

## What's Working

- ✅ Publish interactions
- ✅ Get/search profiles
- ✅ Get/search interactions
- ✅ Set/get configuration
- ✅ Delete profiles/interactions
- ✅ Get feedbacks
- ✅ Profile change logs
- ✅ Regenerate feedbacks

All endpoints work without authentication when `SELF_HOST=true`!
