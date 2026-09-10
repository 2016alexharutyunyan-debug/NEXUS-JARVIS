# Security and privacy

This is experimental desktop-control software. Use it with a standard Windows user account, review proposed actions, and avoid sensitive workflows while sharing the screen.

Do not attach API keys, local settings, conversation history, private screenshots or personal files to public issues. Redact diagnostics before sharing. If a key was exposed, revoke it at its provider and create a new one; deleting a file from the latest Git commit does not remove it from history.

The actual `VOICE_API_KEY.txt`, local environments and runtime state are ignored by Git. `.gitignore` is not a secret scanner; review every commit and archive before publishing. Never publish your entire working directory or AppData folder.

For a security vulnerability, use GitHub's private vulnerability reporting option if enabled on this repository. If it is unavailable, ask the maintainer for a private reporting channel without posting exploit details or secrets publicly.
