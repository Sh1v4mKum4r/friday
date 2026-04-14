"""Plugin-based tool loader for Friday AI.

Each tool is a plain .py file that exports:
  - ``name``        (str)  — unique tool identifier
  - ``description`` (str)  — human-readable description
  - ``run``         (callable) — function that performs the tool action

The loader discovers all qualifying files at startup and can hot-reload
on demand (e.g. when the user types /reload).
"""

from __future__ import annotations

import inspect
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Prefix used when registering dynamically loaded modules into sys.modules.
# Using a unique prefix avoids collisions with installed packages.
_MODULE_PREFIX = "friday_tool_"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """Represents a single discovered tool."""

    name: str
    description: str
    run: Callable
    parameters: dict[str, str] = field(default_factory=dict)
    source_path: Path = field(default_factory=Path)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ToolLoader:
    """Discovers, loads, and executes plugin tools from one or more directories.

    Parameters
    ----------
    tool_dirs:
        List of :class:`~pathlib.Path` objects to scan for tool files.
    """

    def __init__(self, tool_dirs: list[Path], data_dir: Path | None = None) -> None:
        self.tool_dirs = tool_dirs
        # Maps tool name -> Tool instance
        self.tools: dict[str, Tool] = {}
        # Disabled tools — persisted to disk
        self._disabled_file = (data_dir / "disabled_tools.txt") if data_dir else None
        self.disabled: set[str] = self._load_disabled()

    def _load_disabled(self) -> set[str]:
        if self._disabled_file and self._disabled_file.exists():
            return {l.strip() for l in self._disabled_file.read_text().splitlines() if l.strip()}
        return set()

    def _save_disabled(self) -> None:
        if self._disabled_file:
            self._disabled_file.parent.mkdir(parents=True, exist_ok=True)
            self._disabled_file.write_text("\n".join(sorted(self.disabled)) + "\n")

    def disable_tool(self, name: str) -> bool:
        if name in self.tools:
            self.disabled.add(name)
            self._save_disabled()
            return True
        return False

    def enable_tool(self, name: str) -> bool:
        if name in self.disabled:
            self.disabled.discard(name)
            self._save_disabled()
            return True
        return False

    def is_enabled(self, name: str) -> bool:
        return name not in self.disabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> list[Tool]:
        """Scan all *tool_dirs* for .py files and load each as a tool.

        Files whose names start with ``_`` (including ``__init__.py``) are
        silently skipped.  The results are stored in ``self.tools`` and
        returned as a list.
        """
        self.tools.clear()
        for directory in self.tool_dirs:
            if not directory.exists():
                logger.debug("Tool directory %s does not exist, skipping.", directory)
                continue
            for path in sorted(directory.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                try:
                    tool = self._load_tool_file(path)
                    self.tools[tool.name] = tool
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to load tool %s: %s", path, exc)
        return list(self.tools.values())

    def execute(self, tool_name: str, args: dict) -> str:
        """Call the named tool with *args* and return the result as a string.

        Raises
        ------
        KeyError
            If *tool_name* is not found in the loaded tools.
        """
        if tool_name in self.disabled:
            raise KeyError(f"Tool '{tool_name}' is disabled")
        tool = self.tools[tool_name]
        result = tool.run(**args)
        return str(result)

    def reload(self) -> list[Tool]:
        """Clear all loaded tools and re-discover from *tool_dirs*.

        Useful for implementing a ``/reload`` command so that users can drop
        new .py files into the plugins directory without restarting Friday.
        """
        return self.discover()

    def get_tools_description(self) -> str:
        """Return a human-readable summary of all enabled tools.

        Disabled tools are excluded — the LLM should never see them.
        """
        if not self.tools:
            return ""
        lines: list[str] = []
        for tool in self.tools.values():
            if tool.name in self.disabled:
                continue
            params_str = ", ".join(
                f"{name}: {type_hint}" for name, type_hint in tool.parameters.items()
            )
            lines.append(f"- {tool.name}({params_str}): {tool.description}")
        return "\n".join(lines)

    def get_tool_schemas(self) -> list[dict]:
        """Return OpenAI-compatible function schemas for every loaded tool.

        Each schema follows the format expected by the Ollama/OpenAI tool-calling
        API::

            {
                "type": "function",
                "function": {
                    "name": "...",
                    "description": "...",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "param_name": {"type": "string", "description": "param_name"}
                        },
                        "required": ["param_name_without_default", ...]
                    }
                }
            }
        """
        schemas: list[dict] = []
        for tool in self.tools.values():
            if tool.name in self.disabled:
                continue
            sig = inspect.signature(tool.run)
            properties: dict[str, dict] = {}
            required: list[str] = []

            for param_name, param in sig.parameters.items():
                annotation = param.annotation
                if annotation is inspect.Parameter.empty:
                    json_type = "string"
                else:
                    json_type = _python_type_to_json(annotation)

                properties[param_name] = {
                    "type": json_type,
                    "description": param_name,
                }
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return schemas

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_tool_file(self, path: Path) -> Tool:
        """Load a single .py file as a module and extract the Tool metadata.

        The module is registered in ``sys.modules`` under a unique key derived
        from the file path so that repeated loads (hot-reload) replace the
        previous entry rather than accumulating stale copies.

        We compile the source directly (bypassing .pyc bytecode cache) so that
        hot-reload always reflects the latest on-disk content.
        """
        import types as _types

        module_key = _module_key_for_path(path)

        # Remove stale copy before reloading to avoid accumulating duplicates.
        if module_key in sys.modules:
            del sys.modules[module_key]

        # Read and compile source directly — this skips the .pyc cache so that
        # a changed file is always re-evaluated on reload.
        source = path.read_text(encoding="utf-8")
        code = compile(source, str(path), "exec")

        module = _types.ModuleType(module_key)
        module.__file__ = str(path)
        sys.modules[module_key] = module
        exec(code, module.__dict__)  # noqa: S102

        # Validate required attributes
        if not hasattr(module, "name"):
            raise AttributeError(f"Tool file {path} is missing 'name'")
        if not hasattr(module, "description"):
            raise AttributeError(f"Tool file {path} is missing 'description'")
        if not hasattr(module, "run"):
            raise AttributeError(f"Tool file {path} is missing 'run'")

        # Extract parameter info via inspect
        sig = inspect.signature(module.run)
        parameters: dict[str, str] = {}
        for param_name, param in sig.parameters.items():
            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                parameters[param_name] = "any"
            else:
                parameters[param_name] = _annotation_to_str(annotation)

        return Tool(
            name=module.name,
            description=module.description,
            run=module.run,
            parameters=parameters,
            source_path=path,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _module_key_for_path(path: Path) -> str:
    """Return a stable, unique sys.modules key for a given tool file path.

    We use the hex digest of the absolute path string so that two files with
    the same name in different directories don't collide.
    """
    import hashlib

    digest = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]
    stem = path.stem.replace("-", "_")
    return f"{_MODULE_PREFIX}{stem}_{digest}"


def _annotation_to_str(annotation) -> str:
    """Convert a Python type annotation to a short human-readable string."""
    if annotation is inspect.Parameter.empty:
        return "any"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _python_type_to_json(annotation) -> str:
    """Map a Python type to a JSON Schema type string."""
    _MAP: dict[type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    if annotation is inspect.Parameter.empty:
        return "string"
    return _MAP.get(annotation, "string")
