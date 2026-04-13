"""Tests for friday_ai/tool_loader.py — TDD.

All tests use tempfile.TemporaryDirectory with dynamically written .py tool
files so no real filesystem tools are needed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from friday_ai.tool_loader import Tool, ToolLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_tool(directory: Path, filename: str, content: str) -> Path:
    """Write a tool .py file into *directory* and return its path."""
    path = directory / filename
    path.write_text(content)
    return path


SIMPLE_TOOL = """\
name = "say_hello"
description = "Return a hello greeting"

def run(target: str = "world") -> str:
    return f"Hello, {target}!"
"""

ADD_TOOL = """\
name = "add_numbers"
description = "Add two integers"

def run(a: int, b: int) -> str:
    return str(int(a) + int(b))
"""

UNDERSCORE_TOOL = """\
name = "private_tool"
description = "Should be skipped"

def run() -> str:
    return "hidden"
"""


# ---------------------------------------------------------------------------
# 1. Discovery
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_discovers_tool_from_single_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            assert any(t.name == "say_hello" for t in tools)

    def test_returns_list_of_tool_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            assert all(isinstance(t, Tool) for t in tools)

    def test_discovers_multiple_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            write_tool(d, "add.py", ADD_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            names = {t.name for t in tools}
            assert "say_hello" in names
            assert "add_numbers" in names

    def test_skips_underscore_prefixed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "_private.py", UNDERSCORE_TOOL)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            names = {t.name for t in tools}
            assert "private_tool" not in names
            assert "say_hello" in names

    def test_skips_dunder_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # __init__.py should be skipped (starts with _)
            write_tool(d, "__init__.py", UNDERSCORE_TOOL)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            assert len(tools) == 1

    def test_discovers_tools_from_multiple_dirs(self):
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                d1 = Path(tmp1)
                d2 = Path(tmp2)
                write_tool(d1, "hello.py", SIMPLE_TOOL)
                write_tool(d2, "add.py", ADD_TOOL)
                loader = ToolLoader([d1, d2])
                tools = loader.discover()
                names = {t.name for t in tools}
                assert "say_hello" in names
                assert "add_numbers" in names

    def test_discover_stores_in_self_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            assert "say_hello" in loader.tools

    def test_tool_has_correct_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            path = write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            tools = loader.discover()
            tool = next(t for t in tools if t.name == "say_hello")
            assert tool.source_path == path

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader = ToolLoader([Path(tmp)])
            tools = loader.discover()
            assert tools == []

    def test_nonexistent_directory_handled_gracefully(self):
        loader = ToolLoader([Path("/nonexistent/path/xyz")])
        # Should not raise; just return empty
        tools = loader.discover()
        assert tools == []


# ---------------------------------------------------------------------------
# 2. Execution
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            result = loader.execute("say_hello", {"target": "Friday"})
            assert isinstance(result, str)

    def test_execute_returns_correct_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            result = loader.execute("say_hello", {"target": "Friday"})
            assert result == "Hello, Friday!"

    def test_execute_with_default_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            result = loader.execute("say_hello", {})
            assert result == "Hello, world!"

    def test_execute_numeric_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "add.py", ADD_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            result = loader.execute("add_numbers", {"a": 3, "b": 7})
            assert result == "10"

    def test_execute_unknown_tool_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader = ToolLoader([Path(tmp)])
            loader.discover()
            with pytest.raises(KeyError):
                loader.execute("nonexistent_tool", {})


# ---------------------------------------------------------------------------
# 3. Tool descriptions
# ---------------------------------------------------------------------------


class TestGetToolsDescription:
    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            desc = loader.get_tools_description()
            assert isinstance(desc, str)

    def test_contains_tool_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            desc = loader.get_tools_description()
            assert "say_hello" in desc

    def test_contains_tool_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            desc = loader.get_tools_description()
            assert "Return a hello greeting" in desc

    def test_contains_parameter_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            desc = loader.get_tools_description()
            assert "target" in desc

    def test_format_uses_dash_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            desc = loader.get_tools_description()
            assert desc.strip().startswith("-")

    def test_empty_when_no_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader = ToolLoader([Path(tmp)])
            loader.discover()
            desc = loader.get_tools_description()
            assert desc == ""


# ---------------------------------------------------------------------------
# 4. Hot-reload
# ---------------------------------------------------------------------------


class TestReload:
    def test_reload_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            result = loader.reload()
            assert isinstance(result, list)

    def test_reload_picks_up_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            # Add a new tool after initial discovery
            write_tool(d, "add.py", ADD_TOOL)
            tools = loader.reload()
            names = {t.name for t in tools}
            assert "add_numbers" in names

    def test_reload_reflects_changed_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            path = write_tool(d, "greet.py", """\
name = "greet"
description = "Greet someone"

def run() -> str:
    return "version 1"
""")
            loader = ToolLoader([d])
            loader.discover()
            assert loader.execute("greet", {}) == "version 1"

            # Overwrite with new implementation
            path.write_text("""\
name = "greet"
description = "Greet someone"

def run() -> str:
    return "version 2"
""")
            loader.reload()
            assert loader.execute("greet", {}) == "version 2"

    def test_reload_clears_removed_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            path = write_tool(d, "temp_tool.py", """\
name = "temp_tool"
description = "Temporary"

def run() -> str:
    return "here"
""")
            loader = ToolLoader([d])
            loader.discover()
            assert "temp_tool" in loader.tools

            # Remove the file, then reload
            path.unlink()
            loader.reload()
            assert "temp_tool" not in loader.tools

    def test_reload_does_not_stack_duplicate_modules(self):
        """Reloading multiple times must not cause duplicate sys.modules entries."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            before = len([k for k in sys.modules if "friday_tool_" in k])
            loader.reload()
            loader.reload()
            after = len([k for k in sys.modules if "friday_tool_" in k])
            # Should not keep growing unboundedly — count should remain stable
            assert after <= before + 1


# ---------------------------------------------------------------------------
# 5. OpenAI-compatible schemas
# ---------------------------------------------------------------------------


class TestGetToolSchemas:
    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schemas = loader.get_tool_schemas()
            assert isinstance(schemas, list)

    def test_schema_has_type_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            assert schema["type"] == "function"

    def test_schema_has_function_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            assert "function" in schema

    def test_schema_function_has_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            assert schema["function"]["name"] == "say_hello"

    def test_schema_function_has_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            assert "description" in schema["function"]
            assert "greeting" in schema["function"]["description"].lower()

    def test_schema_function_has_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            params = schema["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params

    def test_schema_parameters_include_arg_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            props = schema["function"]["parameters"]["properties"]
            assert "target" in props

    def test_schema_required_list_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "add.py", ADD_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            assert "required" in schema["function"]["parameters"]

    def test_schema_required_excludes_defaulted_params(self):
        """Parameters with defaults should NOT appear in 'required'."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "hello.py", SIMPLE_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            required = schema["function"]["parameters"]["required"]
            # 'target' has a default of "world", so not required
            assert "target" not in required

    def test_schema_required_includes_non_defaulted_params(self):
        """Parameters without defaults MUST appear in 'required'."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_tool(d, "add.py", ADD_TOOL)
            loader = ToolLoader([d])
            loader.discover()
            schema = loader.get_tool_schemas()[0]
            required = schema["function"]["parameters"]["required"]
            assert "a" in required
            assert "b" in required

    def test_empty_tools_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader = ToolLoader([Path(tmp)])
            loader.discover()
            assert loader.get_tool_schemas() == []
