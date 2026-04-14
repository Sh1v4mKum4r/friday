"""Tests for friday_ai/memory.py — written before implementation (TDD)."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from friday_ai.memory import MemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp: Path) -> MemoryStore:
    """Create a MemoryStore backed by a subdirectory of *tmp*."""
    data_dir = tmp / "data"
    data_dir.mkdir()
    return MemoryStore(data_dir=data_dir)


# ---------------------------------------------------------------------------
# 1. Init — directories created on construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_memory_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert store.memory_dir.is_dir()

    def test_history_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert store.history_dir.is_dir()

    def test_memory_dir_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            store = MemoryStore(data_dir=data_dir)
            assert store.memory_dir == data_dir / "memory"

    def test_history_dir_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            store = MemoryStore(data_dir=data_dir)
            assert store.history_dir == data_dir / "history"

    def test_memory_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            store = MemoryStore(data_dir=data_dir)
            assert store.memory_file == store.memory_dir / "MEMORY.md"


# ---------------------------------------------------------------------------
# 2. read_memory
# ---------------------------------------------------------------------------


class TestReadMemory:
    def test_returns_empty_string_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert store.read_memory() == ""

    def test_returns_file_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- remember this\n")
            assert store.read_memory() == "- remember this\n"

    def test_returns_string_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            result = store.read_memory()
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 3. write_memory
# ---------------------------------------------------------------------------


class TestWriteMemory:
    def test_appends_bullet_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("user likes Python")
            contents = store.memory_file.read_text()
            assert "- user likes Python" in contents

    def test_multiple_entries_each_on_own_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("first fact")
            store.write_memory("second fact")
            lines = store.memory_file.read_text().splitlines()
            assert any("first fact" in l for l in lines)
            assert any("second fact" in l for l in lines)

    def test_creates_file_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert not store.memory_file.exists()
            store.write_memory("brand new entry")
            assert store.memory_file.exists()

    def test_existing_entries_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("keep me")
            store.write_memory("and me too")
            text = store.memory_file.read_text()
            assert "keep me" in text
            assert "and me too" in text


# ---------------------------------------------------------------------------
# 4. forget_memory
# ---------------------------------------------------------------------------


class TestForgetMemory:
    def test_removes_line_matching_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- user likes Python\n- user dislikes Java\n")
            store.forget_memory("Java")
            contents = store.memory_file.read_text()
            assert "Java" not in contents

    def test_keeps_non_matching_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- user likes Python\n- user dislikes Java\n")
            store.forget_memory("Java")
            contents = store.memory_file.read_text()
            assert "Python" in contents

    def test_case_insensitive_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- User likes JAVA frameworks\n- something else\n")
            store.forget_memory("java")
            contents = store.memory_file.read_text()
            assert "JAVA" not in contents

    def test_no_error_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            # should not raise
            store.forget_memory("anything")

    def test_removes_multiple_matching_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text(
                "- cats are good\n- dogs are good\n- cats are fluffy\n"
            )
            store.forget_memory("cats")
            contents = store.memory_file.read_text()
            assert "cats" not in contents
            assert "dogs" in contents


# ---------------------------------------------------------------------------
# 5. list_memory
# ---------------------------------------------------------------------------


class TestListMemory:
    def test_returns_list_of_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            result = store.list_memory()
            assert isinstance(result, list)

    def test_empty_list_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert store.list_memory() == []

    def test_parses_bullet_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- item one\n- item two\n")
            items = store.list_memory()
            assert "item one" in items
            assert "item two" in items

    def test_strips_bullet_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- just the text\n")
            items = store.list_memory()
            assert items[0] == "just the text"

    def test_ignores_non_bullet_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("# Header\n- bullet item\nplain line\n")
            items = store.list_memory()
            assert len(items) == 1
            assert items[0] == "bullet item"

    def test_empty_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("")
            assert store.list_memory() == []


# ---------------------------------------------------------------------------
# 6. clear_memory
# ---------------------------------------------------------------------------


class TestClearMemory:
    def test_empties_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.memory_file.write_text("- some fact\n- another fact\n")
            store.clear_memory()
            assert store.memory_file.read_text() == ""

    def test_creates_empty_file_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.clear_memory()
            assert store.memory_file.exists()
            assert store.memory_file.read_text() == ""

    def test_list_memory_empty_after_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("fact a")
            store.write_memory("fact b")
            store.clear_memory()
            assert store.list_memory() == []


# ---------------------------------------------------------------------------
# 7. append_daily_log
# ---------------------------------------------------------------------------


class TestAppendDailyLog:
    def test_creates_log_file_for_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("did something")
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = store.memory_dir / f"{today}.md"
            assert log_file.exists()

    def test_entry_appears_in_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("important event happened")
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = store.memory_dir / f"{today}.md"
            assert "important event happened" in log_file.read_text()

    def test_new_file_gets_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("first entry")
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = store.memory_dir / f"{today}.md"
            contents = log_file.read_text()
            assert f"# {today}" in contents

    def test_existing_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("entry one")
            store.append_daily_log("entry two")
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = store.memory_dir / f"{today}.md"
            contents = log_file.read_text()
            assert "entry one" in contents
            assert "entry two" in contents

    def test_entry_includes_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("timestamped entry")
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = store.memory_dir / f"{today}.md"
            contents = log_file.read_text()
            # Timestamp format like [HH:MM] or [YYYY-MM-DD HH:MM:SS]
            assert "[" in contents and "]" in contents


# ---------------------------------------------------------------------------
# 8. save_session
# ---------------------------------------------------------------------------


class TestSaveSession:
    def test_returns_path_to_saved_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "user", "content": "hello"}]
            result = store.save_session(messages)
            assert isinstance(result, Path)

    def test_file_exists_after_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "user", "content": "hello"}]
            path = store.save_session(messages)
            assert path.exists()

    def test_saved_in_history_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "user", "content": "hello"}]
            path = store.save_session(messages)
            assert path.parent == store.history_dir

    def test_filename_starts_with_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            path = store.save_session([])
            assert path.name.startswith("session-")

    def test_filename_is_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            path = store.save_session([])
            assert path.suffix == ".json"

    def test_messages_saved_in_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "assistant", "content": "hi there"}]
            path = store.save_session(messages)
            data = json.loads(path.read_text())
            assert data["messages"] == messages

    def test_timestamp_field_in_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            path = store.save_session([])
            data = json.loads(path.read_text())
            assert "timestamp" in data

    def test_empty_messages_list_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            path = store.save_session([])
            data = json.loads(path.read_text())
            assert data["messages"] == []


# ---------------------------------------------------------------------------
# 9. load_latest_session
# ---------------------------------------------------------------------------


class TestLoadLatestSession:
    def test_returns_none_when_no_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            assert store.load_latest_session() is None

    def test_returns_list_of_dicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "user", "content": "hello"}]
            store.save_session(messages)
            result = store.load_latest_session()
            assert isinstance(result, list)

    def test_loads_saved_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            messages = [{"role": "user", "content": "test message"}]
            store.save_session(messages)
            result = store.load_latest_session()
            assert result == messages

    def test_loads_most_recent_when_multiple_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.save_session([{"role": "user", "content": "older"}])
            import time; time.sleep(1)  # ensure different timestamps
            store.save_session([{"role": "user", "content": "newer"}])
            result = store.load_latest_session()
            assert result == [{"role": "user", "content": "newer"}]

    def test_ignores_non_json_files_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            (store.history_dir / "not-a-session.txt").write_text("random")
            assert store.load_latest_session() is None


# ---------------------------------------------------------------------------
# 10. get_context_for_prompt
# ---------------------------------------------------------------------------


class TestGetContextForPrompt:
    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            result = store.get_context_for_prompt()
            assert isinstance(result, str)

    def test_includes_memory_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("user prefers dark mode")
            result = store.get_context_for_prompt()
            assert "user prefers dark mode" in result

    def test_today_log_found_via_query_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("asked about the weather")
            result = store.get_context_for_prompt(query="weather forecast")
            assert "weather" in result.lower()

    def test_returns_empty_string_when_both_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            result = store.get_context_for_prompt()
            assert result == ""

    def test_memory_section_label_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.write_memory("a fact")
            result = store.get_context_for_prompt()
            assert "Memory" in result

    def test_daily_log_searched_when_query_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            store.append_daily_log("discussed proxy config")
            result = store.get_context_for_prompt(query="proxy setup")
            assert "proxy" in result.lower()
