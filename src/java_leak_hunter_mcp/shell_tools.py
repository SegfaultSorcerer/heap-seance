from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class ToolingMissingError(RuntimeError):
    pass


class CommandExecutionError(RuntimeError):
    pass


def which(binary: str) -> str | None:
    return shutil.which(binary)


def require_binary(binary: str, install_hint: str) -> str:
    location = which(binary)
    if not location:
        raise ToolingMissingError(
            f"Missing required binary '{binary}'. {install_hint}"
        )
    return location


def require_any_binary(candidates: Sequence[str], install_hint: str) -> str:
    for candidate in candidates:
        location = which(candidate)
        if location:
            return location
    joined = ", ".join(candidates)
    raise ToolingMissingError(
        f"Missing required binary. Tried: {joined}. {install_hint}"
    )


def run_command(
    command: Sequence[str],
    *,
    timeout_s: int = 180,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    base_env = os.environ.copy()
    if env:
        base_env.update(env)

    try:
        proc = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd,
            env=base_env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pretty = " ".join(shlex.quote(part) for part in command)
        raise CommandExecutionError(
            f"Command timed out after {timeout_s}s: {pretty}"
        ) from exc

    return CommandResult(
        command=list(command),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def ensure_success(result: CommandResult) -> CommandResult:
    if result.returncode == 0:
        return result

    pretty = " ".join(shlex.quote(part) for part in result.command)
    stderr = result.stderr.strip() or "<empty>"
    stdout = result.stdout.strip() or "<empty>"
    raise CommandExecutionError(
        f"Command failed ({result.returncode}): {pretty}\nstdout: {stdout}\nstderr: {stderr}"
    )
