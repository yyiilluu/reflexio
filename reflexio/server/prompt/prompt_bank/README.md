# /user_profiler/reflexio/server/prompt/prompt_bank
Description: File-based versioned prompt templates for LLM operations

## Main Entry Points

- **Manager**: `../prompt_manager.py` - `PromptManager`
- **Templates**: Each subdirectory is a prompt_id

## Directory Structure

```
prompt_bank/
├── profile_update_main/
│   ├── metadata.json     # Version info and variables
│   └── 1.0.1.prompt      # Template content
├── feedback_extraction/
├── shadow_content_evaluation/
└── ... (other prompts)
```

## Metadata Schema

```json
{
  "prompt_id": "my_prompt",
  "active_version": "1.0.0",
  "description": "What this prompt does",
  "versions": {
    "1.0.0": {
      "created_at": 1703123456,
      "variables": ["var1", "var2"]
    }
  }
}
```

## Usage

```python
# Access via request_context
rendered = request_context.prompt_manager.render_prompt(
    "profile_update_main",
    {"variable1": "value1", "variable2": "value2"}
)
```

## Adding New Prompt

1. Create directory: `mkdir prompt_bank/my_new_prompt/`
2. Create prompt file: `1.0.0.prompt` with `{variable}` placeholders
3. Create `metadata.json` with version info

## Version Naming Convention

Versions follow semantic versioning: `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

- **First digit (MAJOR)**: Breaking changes that introduce a different set of variables
- **Second digit (MINOR)**: Significant updates without changing variables in metadata.json
- **Third digit (PATCH)**: Minor updates/tweaks to the prompt content

## Key Rules

- **Prompt ID** = Directory name
- **Variables** use `{variable_name}` syntax
- **NEVER hardcode prompts** - Always use PromptManager
