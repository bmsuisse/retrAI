"""Safety guardrails — configurable limits and dangerous-operation detection."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(StrEnum):
    """Risk levels for operations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyConfig:
    """Configurable safety settings.

    Can be loaded from the `safety` section of `.retrai.yml`.
    """

    max_file_size_mb: float = 10.0
    max_concurrent_requests: int = 5
    max_download_size_mb: float = 50.0
    max_execution_time_seconds: int = 300
    allow_network_access: bool = True
    require_approval_above: RiskLevel = RiskLevel.HIGH
    blocked_commands: list[str] = field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf ~",
            "rm -rf /*",
            "mkfs",
            "dd if=",
            ":(){:|:&};:",
            "chmod -R 777 /",
            "curl | sh",
            "wget | sh",
            "curl | bash",
            "wget | bash",
        ]
    )
    allowed_domains: list[str] = field(
        default_factory=lambda: [
            "ncbi.nlm.nih.gov",
            "eutils.ncbi.nlm.nih.gov",
            "arxiv.org",
            "export.arxiv.org",
            "huggingface.co",
            "raw.githubusercontent.com",
            "data.gov",
            "zenodo.org",
            "figshare.com",
            "kaggle.com",
            "openalex.org",
            "api.openalex.org",
            "api.semanticscholar.org",
            "api.crossref.org",
            "pypi.org",
            "npmjs.com",
            "registry.npmjs.org",
        ]
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyConfig:
        """Create config from a dictionary (e.g. from .retrai.yml)."""
        config = cls()
        if "max_file_size_mb" in data:
            config.max_file_size_mb = float(data["max_file_size_mb"])
        if "max_download_size_mb" in data:
            config.max_download_size_mb = float(data["max_download_size_mb"])
        if "max_execution_time_seconds" in data:
            config.max_execution_time_seconds = int(data["max_execution_time_seconds"])
        if "allow_network_access" in data:
            config.allow_network_access = bool(data["allow_network_access"])
        if "require_approval_above" in data:
            config.require_approval_above = RiskLevel(data["require_approval_above"])
        if "blocked_commands" in data:
            config.blocked_commands.extend(data["blocked_commands"])
        if "allowed_domains" in data:
            config.allowed_domains.extend(data["allowed_domains"])
        return config


@dataclass
class SafetyViolation:
    """A detected safety violation."""

    rule: str
    description: str
    risk_level: RiskLevel
    blocked: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "blocked": self.blocked,
        }


# Dangerous patterns in shell commands
_DANGEROUS_PATTERNS: list[tuple[str, str, RiskLevel]] = [
    # (regex_pattern, description, risk_level)
    (
        r"\brm\s+(-[rf]+\s+)*(/|~/|\$HOME)",
        "Recursive deletion of system/home directory",
        RiskLevel.CRITICAL,
    ),
    (r"\bmkfs\b", "Filesystem format command", RiskLevel.CRITICAL),
    (r"\bdd\s+if=", "Raw disk write", RiskLevel.CRITICAL),
    (r":\(\)\{.*\}", "Fork bomb", RiskLevel.CRITICAL),
    (r"\bchmod\s+-R\s+777\s+/", "Recursive permission change on root", RiskLevel.CRITICAL),
    (r"\bcurl\b.*\|\s*(sh|bash)\b", "Remote code execution via curl", RiskLevel.HIGH),
    (r"\bwget\b.*\|\s*(sh|bash)\b", "Remote code execution via wget", RiskLevel.HIGH),
    (r"\bnc\s+-[le]", "Netcat listener (potential backdoor)", RiskLevel.HIGH),
    (r"\bsudo\b", "Privileged command execution", RiskLevel.MEDIUM),
    (r"\bsystemctl\s+(stop|disable|mask)", "Stopping system services", RiskLevel.MEDIUM),
    (r"\bkill\s+-9", "Force kill process", RiskLevel.LOW),
    (r"\brm\s+-rf\b", "Recursive force deletion", RiskLevel.MEDIUM),
]

# Dangerous patterns in Python code
_DANGEROUS_PYTHON_PATTERNS: list[tuple[str, str, RiskLevel]] = [
    (r"\bos\.system\b", "OS command execution in Python", RiskLevel.MEDIUM),
    (r"\bsubprocess\.call\b.*shell\s*=\s*True", "Shell subprocess in Python", RiskLevel.MEDIUM),
    (r"\bshutil\.rmtree\s*\(\s*['\"]?/", "Deleting root directory tree", RiskLevel.CRITICAL),
    (r"\bopen\s*\(\s*['\"]?/etc/", "Reading system configuration files", RiskLevel.LOW),
    (r"\bsocket\.socket\b", "Raw socket creation", RiskLevel.MEDIUM),
    (r"\b__import__\s*\(\s*['\"]?ctypes", "Loading native C library", RiskLevel.HIGH),
]


class SafetyGuard:
    """Checks tool calls against safety rules before execution.

    Usage:
        guard = SafetyGuard()
        violations = guard.check_bash("rm -rf /")
        if violations:
            for v in violations:
                print(f"⚠️ {v.description} [{v.risk_level.value}]")
    """

    def __init__(self, config: SafetyConfig | None = None) -> None:
        self.config = config or SafetyConfig()

    def check_bash(self, command: str) -> list[SafetyViolation]:
        """Check a bash command for safety violations."""
        violations: list[SafetyViolation] = []

        # Check against blocked commands (substring match)
        for blocked in self.config.blocked_commands:
            if blocked.lower() in command.lower():
                violations.append(
                    SafetyViolation(
                        rule="blocked_command",
                        description=f"Blocked command pattern detected: '{blocked}'",
                        risk_level=RiskLevel.CRITICAL,
                    )
                )

        # Check against regex patterns
        for pattern, desc, risk in _DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(
                    SafetyViolation(
                        rule="dangerous_pattern",
                        description=desc,
                        risk_level=risk,
                    )
                )

        return violations

    def check_python(self, code: str) -> list[SafetyViolation]:
        """Check Python code for safety violations."""
        violations: list[SafetyViolation] = []

        for pattern, desc, risk in _DANGEROUS_PYTHON_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                violations.append(
                    SafetyViolation(
                        rule="dangerous_python",
                        description=desc,
                        risk_level=risk,
                    )
                )

        return violations

    def check_url(self, url: str) -> list[SafetyViolation]:
        """Check a URL against the allowed domains list."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.hostname or ""

        is_allowed = any(
            domain == d or domain.endswith(f".{d}") for d in self.config.allowed_domains
        )

        if not is_allowed:
            return [
                SafetyViolation(
                    rule="untrusted_domain",
                    description=f"Domain '{domain}' is not in the allowed domains list",
                    risk_level=RiskLevel.MEDIUM,
                    blocked=True,
                )
            ]

        return []

    def check_file_size(self, size_bytes: int) -> list[SafetyViolation]:
        """Check if a file size exceeds limits."""
        max_bytes = int(self.config.max_file_size_mb * 1024 * 1024)
        if size_bytes > max_bytes:
            return [
                SafetyViolation(
                    rule="file_too_large",
                    description=(
                        f"File size ({size_bytes / 1024 / 1024:.1f} MB) exceeds "
                        f"limit ({self.config.max_file_size_mb} MB)"
                    ),
                    risk_level=RiskLevel.MEDIUM,
                )
            ]
        return []

    def check_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> list[SafetyViolation]:
        """Check any tool call for safety violations.

        This is the main entry point — call this before dispatching
        any tool in the act node.
        """
        violations: list[SafetyViolation] = []

        if tool_name == "bash_exec":
            command = args.get("command", "")
            violations.extend(self.check_bash(command))

        elif tool_name == "python_exec":
            code = args.get("code", "")
            violations.extend(self.check_python(code))

        elif tool_name == "js_exec":
            code = args.get("code", "")
            # JS can also execute shell commands
            if "child_process" in code or "execSync" in code:
                violations.append(
                    SafetyViolation(
                        rule="js_shell_exec",
                        description="JavaScript code attempts to execute shell commands",
                        risk_level=RiskLevel.MEDIUM,
                    )
                )

        elif tool_name == "dataset_fetch":
            source = args.get("source", "")
            if source == "url":
                url = args.get("query", "")
                violations.extend(self.check_url(url))

        elif tool_name == "file_write":
            content = args.get("content", "")
            size = len(content.encode("utf-8", errors="replace"))
            violations.extend(self.check_file_size(size))

        elif tool_name == "file_delete":
            path = args.get("path", "")
            violations.extend(self.check_file_delete(path))

        return violations

    def check_file_delete(self, path: str) -> list[SafetyViolation]:
        """Check if a file deletion targets critical project files."""
        critical_files = {
            ".retrai.yml",
            ".git",
            ".gitignore",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "Makefile",
            "LICENSE",
        }
        # Normalise: strip leading ./ and trailing /
        normalised = path.lstrip("./").rstrip("/")
        basename = normalised.split("/")[-1] if "/" in normalised else normalised

        if normalised in critical_files or basename in critical_files:
            return [
                SafetyViolation(
                    rule="critical_file_delete",
                    description=(
                        f"Attempted to delete critical project file: '{path}'"
                    ),
                    risk_level=RiskLevel.HIGH,
                )
            ]
        if normalised == ".git" or normalised.startswith(".git/"):
            return [
                SafetyViolation(
                    rule="git_delete",
                    description="Attempted to delete .git directory or its contents",
                    risk_level=RiskLevel.CRITICAL,
                )
            ]
        return []

    def should_block(self, violations: list[SafetyViolation]) -> bool:
        """Determine if violations should block execution."""
        if not violations:
            return False

        threshold = self.config.require_approval_above
        level_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        threshold_idx = level_order.index(threshold)

        for v in violations:
            v_idx = level_order.index(v.risk_level)
            if v_idx >= threshold_idx:
                return True

        return False

    def format_violations(self, violations: list[SafetyViolation]) -> str:
        """Format violations into a human-readable string."""
        if not violations:
            return ""

        icons = {
            RiskLevel.LOW: "ℹ️",
            RiskLevel.MEDIUM: "⚠️",
            RiskLevel.HIGH: "🚨",
            RiskLevel.CRITICAL: "🛑",
        }

        lines = ["## Safety Check Results\n"]
        for v in violations:
            icon = icons.get(v.risk_level, "•")
            status = "BLOCKED" if v.blocked else "WARNING"
            lines.append(f"- {icon} [{status}] {v.description} (risk: {v.risk_level.value})")

        return "\n".join(lines)


def load_safety_config(cwd: str) -> SafetyConfig:
    """Load safety config from .retrai.yml if available."""
    from retrai.config import load_config

    config_data = load_config(cwd)
    if config_data and "safety" in config_data:
        return SafetyConfig.from_dict(config_data["safety"])
    return SafetyConfig()
