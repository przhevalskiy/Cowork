from .claude_provider import ClaudeProvider


def get_claude_provider(api_key: str, model: str) -> ClaudeProvider:
    return ClaudeProvider(api_key=api_key, model=model)


__all__ = ["ClaudeProvider", "get_claude_provider"]
