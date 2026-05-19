"""AgentGuard — AI Output Safety Engine.

Three-layer progressive guard: Schema -> Semantic -> Policy.
"""

from agentguard.result import GuardLevel, CheckResult, GuardResult
from agentguard.guard import Guard

__version__ = "0.1.0"
__all__ = ["Guard", "GuardLevel", "CheckResult", "GuardResult"]
