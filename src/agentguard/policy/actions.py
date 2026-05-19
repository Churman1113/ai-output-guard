"""Policy action definitions — what happens when a rule matches."""

from agentguard.result import GuardLevel

# Map action string to GuardLevel
ACTION_TO_LEVEL: dict[str, GuardLevel] = {
    "allow": GuardLevel.PASS,
    "deny": GuardLevel.DENY,
    "warn": GuardLevel.WARN,
    "ask_human": GuardLevel.ASK_HUMAN,
    "modify": GuardLevel.FIX,
}

# Valid action names
VALID_ACTIONS: set[str] = set(ACTION_TO_LEVEL.keys())


def action_to_level(action: str) -> GuardLevel:
    """Convert action string to GuardLevel.
    
    Args:
        action: One of "allow", "deny", "warn", "ask_human", "modify".
    
    Returns:
        Corresponding GuardLevel.
    
    Raises:
        ValueError: If action is not valid.
    """
    level = ACTION_TO_LEVEL.get(action)
    if level is None:
        raise ValueError(
            f"Unknown action '{action}'. Valid: {', '.join(sorted(VALID_ACTIONS))}"
        )
    return level
