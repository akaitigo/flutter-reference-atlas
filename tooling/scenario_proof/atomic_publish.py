#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish one Evidence directory as a validated, rollback-safe bundle."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Callable


Builder = Callable[[Path], None]
Validator = Callable[[Path], None]
Rename = Callable[[Path, Path], None]


def atomic_publish_directory(
    output: Path,
    build: Builder,
    validate: Validator,
    *,
    rename: Rename = os.rename,
) -> None:
    """Build and validate in staging, then replace output with rollback."""
    if output.name in {"", ".", ".."}:
        raise ValueError("Evidence output directory name is unsafe")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
    retained_previous = False
    committed = False
    try:
        build(staging)
        validate(staging)
        if output.exists():
            rename(output, backup)
            retained_previous = True
        try:
            rename(staging, output)
            committed = True
        except BaseException:
            if output.exists():
                shutil.rmtree(output)
            if retained_previous:
                rename(backup, output)
                retained_previous = False
            raise
        if retained_previous:
            shutil.rmtree(backup)
            retained_previous = False
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if retained_previous and not committed and not output.exists():
            rename(backup, output)
