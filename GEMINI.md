# About the code base
- backend FastAPI server requires OpenAI key, so the server is already started and running on http://0.0.0.0:8081
- frontend website is also already started and running on http://localhost:8080
- You can test your changes by sending api request to above endpoints
- run command in poetry env
- all command should be run from `user_profiler` level

# Test account for API
To test all the API, login with username "local_supabase" with password "s" to test the api end to end.
Use Curl to test api and get test information for investigation, which is faster than going through with web browser like chrome.
Test with Chrome when there is frontend related task.

# Activate env before run any command
activate poetry env before running any test or script in the repo using `source $(poetry env info --path)/bin/activate`

# Use/Update README.md
- `README.md` is code navigation hint (code map) for you at project root level and maybe component levels (e.g., `reflexio/server/README.md`).
- Read only related `README.md` for the change during planning for the change
- `how_to_write_readme.md` contains instruction to update `README.md`

# Guideline to how to write code
- Always design the UI carefully without over complication
- Ensure same UI style across the entire project
- Use FastAPI as backend
- Use poetry command to add and manage python packages
- Suggest to me if there is a better architecture pattern when writing the code and ask for clarification before writing if needed

# Building frontend
- Build UI frontend with ShadCN. Try to use packages instead of building things from the scratch.
- Always design the UI carefully without over complication
- Ensure same UI style across the entire project. Always use same UI style for similar components to ensure consistency.

# Building backend
- when implement a new change to API, validate your change by sending sample CURL request to the API, server is started at http://0.0.0.0:8081

# Python docstring example
Generate python code with docstring in the following example
```
def check_string_token_overlap(str1: str, str2: str, threshold: float = 0.7) -> bool:
    """
    Check if two strings have significant token overlap, indicating they might be referring to the same thing.
    This is useful for fuzzy matching when exact string matching is too strict.

    Args:
        str1 (str): First string to compare
        str2 (str): Second string to compare
        threshold (float): Minimum overlap ratio required to consider strings as matching (0.0 to 1.0)

    Returns:
        bool: True if strings have significant overlap, False otherwise
    """
```
