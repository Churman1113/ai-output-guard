"""Built-in dangerous intent registry.

Defines 5 categories with 20+ sub-classes of dangerous AI outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntentCategory(str, Enum):
    DATA_DESTRUCTION = "data_destruction"
    SYSTEM_OPERATION = "system_operation"
    NETWORK_RISK = "network_risk"
    CREDENTIAL_LEAK = "credential_leak"
    COMPLIANCE_RISK = "compliance_risk"


@dataclass
class Intent:
    """A dangerous intent definition."""
    name: str
    category: IntentCategory
    severity: str  # "critical" | "high" | "medium" | "low"
    keywords: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)  # regex patterns
    description: str = ""


# Built-in intent library
BUILTIN_INTENTS: list[Intent] = [
    # === Data Destruction ===
    Intent(
        name="drop_table",
        category=IntentCategory.DATA_DESTRUCTION,
        severity="critical",
        keywords=["drop table", "drop database", "drop schema"],
        patterns=[r"\bDROP\s+TABLE\b", r"\bDROP\s+DATABASE\b", r"\bDROP\s+SCHEMA\b"],
        description="SQL DROP operation — permanent data loss",
    ),
    Intent(
        name="delete_all",
        category=IntentCategory.DATA_DESTRUCTION,
        severity="critical",
        keywords=["delete from", "delete all"],
        patterns=[
            r"\bDELETE\s+FROM\s+\w+\s*$",  # DELETE FROM table (no WHERE)
            r"\bDELETE\s+FROM\s+\w+(?!\s+WHERE)",
        ],
        description="DELETE without WHERE clause — all rows removed",
    ),
    Intent(
        name="truncate",
        category=IntentCategory.DATA_DESTRUCTION,
        severity="critical",
        keywords=["truncate table", "truncate"],
        patterns=[r"\bTRUNCATE\s+(TABLE\s+)?\w+"],
        description="TRUNCATE operation — irreversible data deletion",
    ),
    Intent(
        name="rm_recursive",
        category=IntentCategory.DATA_DESTRUCTION,
        severity="critical",
        keywords=["rm -rf", "rm -r", "rmdir /s", "rmdir /q"],
        patterns=[
            r"\brm\s+-rf?\b",
            r"\brmdir\s+/[sq]\b",
            r"\bRemove-Item\s+-Recurse\s+-Force\b",
        ],
        description="Recursive file deletion — destroys file system data",
    ),

    # === System Operations ===
    Intent(
        name="execute_shell",
        category=IntentCategory.SYSTEM_OPERATION,
        severity="high",
        keywords=[
            "os.system", "subprocess.run", "subprocess.call",
            "subprocess.Popen", "exec(", "eval(",
            "Runtime.getRuntime().exec",
        ],
        patterns=[
            r"\bos\.system\s*\(",
            r"\bsubprocess\.(?:run|call|Popen)\s*\(",
            r"\beval\s*\(",
            r"\bexec\s*\(",
            r"\bRuntime\.getRuntime\(\)\.exec",
        ],
        description="Arbitrary shell/command execution — can run any system command",
    ),
    Intent(
        name="ssh_connect",
        category=IntentCategory.SYSTEM_OPERATION,
        severity="high",
        keywords=["ssh ", "scp ", "paramiko", "fabric.Connection"],
        patterns=[r"\bssh\s+\w+@", r"\bparamiko\.", r"\bfabric\.Connection\b"],
        description="SSH connection establishment — remote system access",
    ),
    Intent(
        name="sudo",
        category=IntentCategory.SYSTEM_OPERATION,
        severity="high",
        keywords=["sudo ", "sudoers"],
        patterns=[r"\bsudo\s+"],
        description="Privilege escalation via sudo",
    ),
    Intent(
        name="modify_system",
        category=IntentCategory.SYSTEM_OPERATION,
        severity="high",
        keywords=[
            "chmod 777", "chmod -R", "chown root",
            "iptables -F", "systemctl stop", "service stop",
            "kubectl delete", "docker rm -f",
            "Write-Output", "Set-Content", "Out-File",
        ],
        patterns=[
            r"\bchmod\s+(-R\s+)?777\b",
            r"\bchown\s+root\b",
            r"\biptables\s+-F\b",
            r"\bkubectl\s+delete\b",
            r"\bdocker\s+rm\s+-f\b",
        ],
        description="Dangerous system modification operations",
    ),

    # === Network Risk ===
    Intent(
        name="send_email",
        category=IntentCategory.NETWORK_RISK,
        severity="medium",
        keywords=["smtplib", "sendmail", "send_mail", "EmailMessage"],
        patterns=[r"\bsmtplib\.SMTP\b", r"\bsendmail\s*\(", r"\bEmailMessage\b"],
        description="Sending emails — potential data exfiltration channel",
    ),
    Intent(
        name="external_request",
        category=IntentCategory.NETWORK_RISK,
        severity="medium",
        keywords=["requests.post", "requests.get", "urllib.request", "curl "],
        patterns=[
            r"\brequests\.(?:post|get|put|delete|patch)\s*\(",
            r"\burllib\.request\b",
            r"\bcurl\s+",
            r"\bfetch\s*\(",
        ],
        description="External HTTP request — potential data exfiltration",
    ),
    Intent(
        name="data_exfiltration",
        category=IntentCategory.NETWORK_RISK,
        severity="high",
        keywords=[
            "base64.b64encode", "base64 encode", "gzip.compress",
            "tarfile.open", "zipfile.ZipFile",
            "export to", "upload to", "send to external",
            "scp ", "rsync ",
        ],
        patterns=[
            r"\bscp\s+",
            r"\brsync\s+",
            r"\bbase64\.b64encode\b",
            r"\bzipfile\.ZipFile\b",
        ],
        description="Data encoding/packaging for potential exfiltration",
    ),

    # === Credential & Secret Leak ===
    Intent(
        name="access_secret",
        category=IntentCategory.CREDENTIAL_LEAK,
        severity="critical",
        keywords=[
            "os.environ", "os.getenv", "process.env",
            "Secret", "keychain", "credential",
            "aws_access_key", "GITHUB_TOKEN",
        ],
        patterns=[
            r"\bos\.(?:environ|getenv)\s*\(",
            r"\bprocess\.env\b",
            r"\baws_access_key_id\b",
            r"\bapi[_\s-]?key\b",
            r"\bsecret[_\s-]?(?:key|token|access)\b",
            r"\bpassword\s*[:=]\s*['\"]?\S+",
        ],
        description="Accessing environment secrets or credentials",
    ),
    Intent(
        name="expose_api_key",
        category=IntentCategory.CREDENTIAL_LEAK,
        severity="critical",
        keywords=[
            "print(api_key)", "console.log(token)", "echo $TOKEN",
            "cat .env", "cat config.json",
            "export API_KEY", "export TOKEN",
        ],
        patterns=[
            r"\bprint\s*\(.*api[_\s-]?key",
            r"\bconsole\.log\s*\(.*token",
            r"\becho\s+\$?\w*TOKEN",
            r"\bcat\s+\.env\b",
            r"\bexport\s+\w*(?:KEY|TOKEN|SECRET)\s*=",
        ],
        description="Exposing API keys or tokens in output",
    ),

    # === Compliance Risk ===
    Intent(
        name="pii_exposure",
        category=IntentCategory.COMPLIANCE_RISK,
        severity="high",
        keywords=[],
        patterns=[
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{16}\b",               # Credit card (simple)
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
        description="Potentially exposing personally identifiable information",
    ),
    Intent(
        name="hallucinated_api",
        category=IntentCategory.COMPLIANCE_RISK,
        severity="medium",
        keywords=[],
        patterns=[
            r"\bfrom\s+(?:openai|anthropic|google)\.(?:non_existent|fake|mock)",
        ],
        description="Using hallucinated/non-existent API endpoints",
    ),
    Intent(
        name="bias_output",
        category=IntentCategory.COMPLIANCE_RISK,
        severity="medium",
        keywords=[],
        patterns=[],
        description="Output that may contain biased or discriminatory content",
    ),
]


class IntentRegistry:
    """Registry for looking up and matching intents."""

    def __init__(self, intents: list[Intent] | None = None):
        self._intents: dict[str, Intent] = {}
        for intent in (intents or BUILTIN_INTENTS):
            self.register(intent)

    def register(self, intent: Intent) -> None:
        self._intents[intent.name] = intent

    def get(self, name: str) -> Intent | None:
        return self._intents.get(name)

    def list_names(self) -> list[str]:
        return list(self._intents.keys())

    def list_by_category(self, category: IntentCategory) -> list[Intent]:
        return [i for i in self._intents.values() if i.category == category]

    def list_critical(self) -> list[Intent]:
        return [i for i in self._intents.values() if i.severity == "critical"]

    def __len__(self) -> int:
        return len(self._intents)

    def __contains__(self, name: str) -> bool:
        return name in self._intents
