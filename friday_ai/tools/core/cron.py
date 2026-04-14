"""Cron job management tool for Friday.

Allows Friday to schedule, list, and remove recurring tasks using the user's crontab.
"""

import subprocess
import re

name = "cron"
description = (
    "Manage scheduled tasks (cron jobs). "
    "Actions: 'list' to show all jobs, "
    "'add <schedule> <command>' to add a job (e.g. 'add 0 9 * * * ~/scripts/backup.sh'), "
    "'remove <pattern>' to remove jobs matching a pattern, "
    "'explain <schedule>' to explain a cron schedule in plain English."
)

# Map human-readable shortcuts to cron schedules
_SHORTCUTS = {
    "every minute": "* * * * *",
    "every hour": "0 * * * *",
    "every day": "0 0 * * *",
    "every morning": "0 9 * * *",
    "every night": "0 22 * * *",
    "every monday": "0 9 * * 1",
    "every tuesday": "0 9 * * 2",
    "every wednesday": "0 9 * * 3",
    "every thursday": "0 9 * * 4",
    "every friday": "0 9 * * 5",
    "every saturday": "0 9 * * 6",
    "every sunday": "0 9 * * 0",
    "every weekday": "0 9 * * 1-5",
    "every weekend": "0 10 * * 6,0",
    "every reboot": "@reboot",
}


def _get_crontab() -> str:
    """Read the current user's crontab."""
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            if "no crontab" in result.stderr.lower():
                return ""
            return ""
        return result.stdout
    except Exception:
        return ""


def _set_crontab(content: str) -> str:
    """Write content as the user's crontab."""
    try:
        proc = subprocess.Popen(
            ["crontab", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        stdout, stderr = proc.communicate(input=content, timeout=5)
        if proc.returncode == 0:
            return "Done."
        return f"Error: {stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"


def _explain_field(value: str, field_name: str, names: dict | None = None) -> str:
    """Explain a single cron field."""
    if value == "*":
        return f"every {field_name}"
    if value.startswith("*/"):
        return f"every {value[2:]} {field_name}s"
    if "," in value:
        parts = value.split(",")
        if names:
            parts = [names.get(p, p) for p in parts]
        return f"{field_name}s: {', '.join(parts)}"
    if "-" in value:
        start, end = value.split("-", 1)
        if names:
            start = names.get(start, start)
            end = names.get(end, end)
        return f"{field_name}s {start} through {end}"
    if names and value in names:
        return f"{field_name} {names[value]}"
    return f"{field_name} {value}"


def _explain_schedule(schedule: str) -> str:
    """Convert a cron schedule to plain English."""
    if schedule.startswith("@"):
        specials = {
            "@reboot": "on every reboot",
            "@hourly": "every hour",
            "@daily": "every day at midnight",
            "@weekly": "every Sunday at midnight",
            "@monthly": "first day of every month at midnight",
            "@yearly": "every January 1st at midnight",
        }
        return specials.get(schedule, schedule)

    parts = schedule.split()
    if len(parts) < 5:
        return schedule

    minute, hour, dom, month, dow = parts[:5]

    dow_names = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat", "7": "Sun"}
    month_names = {"1": "Jan", "2": "Feb", "3": "Mar", "4": "Apr", "5": "May", "6": "Jun",
                   "7": "Jul", "8": "Aug", "9": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}

    desc = []
    if minute == "0" and hour != "*":
        desc.append(f"at {hour}:00")
    elif minute != "*" and hour != "*":
        desc.append(f"at {hour}:{minute.zfill(2)}")
    elif minute.startswith("*/"):
        desc.append(f"every {minute[2:]} minutes")
    elif hour.startswith("*/"):
        desc.append(f"every {hour[2:]} hours")

    if dow != "*":
        desc.append(_explain_field(dow, "day", dow_names))
    if dom != "*":
        desc.append(f"on day {dom} of the month")
    if month != "*":
        desc.append(_explain_field(month, "month", month_names))

    return ", ".join(desc) if desc else "every minute"


def run(action: str) -> str:
    """Manage cron jobs.

    Parameters
    ----------
    action:
        One of:
        - 'list' — show all cron jobs
        - 'add <schedule> <command>' — add a new cron job
        - 'remove <pattern>' — remove jobs matching pattern
        - 'explain <schedule>' — explain a cron schedule
    """
    parts = action.strip().split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "list":
        crontab = _get_crontab()
        if not crontab.strip():
            return "No cron jobs scheduled."
        lines = [l for l in crontab.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            return "No cron jobs scheduled."
        result = []
        for i, line in enumerate(lines, 1):
            sched_parts = line.split(None, 5)
            if len(sched_parts) >= 6:
                sched = " ".join(sched_parts[:5])
                command = sched_parts[5]
                explanation = _explain_schedule(sched)
                result.append(f"{i}. [{explanation}] {command}")
            else:
                result.append(f"{i}. {line}")
        return "\n".join(result)

    elif cmd == "add":
        if not arg:
            return "Usage: add <schedule> <command>\nExample: add 0 9 * * * ~/scripts/backup.sh\nShortcuts: 'every morning', 'every hour', 'every weekday'"

        # Check for shortcuts
        for shortcut, schedule in _SHORTCUTS.items():
            if arg.lower().startswith(shortcut):
                command = arg[len(shortcut):].strip()
                if not command:
                    return f"Usage: add {shortcut} <command>"
                new_line = f"{schedule} {command}"
                crontab = _get_crontab().rstrip("\n")
                crontab += f"\n# Added by Friday\n{new_line}\n"
                result = _set_crontab(crontab)
                return f"Scheduled: {command} ({_explain_schedule(schedule)})\n{result}"

        # Parse raw cron format: first 5 fields are schedule, rest is command
        sched_parts = arg.split(None, 5)
        if len(sched_parts) < 6:
            return "Error: need 5 schedule fields + command.\nExample: add 0 9 * * * /path/to/script.sh"

        schedule = " ".join(sched_parts[:5])
        command = sched_parts[5]
        new_line = f"{schedule} {command}"
        crontab = _get_crontab().rstrip("\n")
        crontab += f"\n# Added by Friday\n{new_line}\n"
        result = _set_crontab(crontab)
        return f"Scheduled: {command} ({_explain_schedule(schedule)})\n{result}"

    elif cmd == "remove":
        if not arg:
            return "Usage: remove <pattern>\nExample: remove backup.sh"
        crontab = _get_crontab()
        lines = crontab.splitlines()
        original_count = len([l for l in lines if l.strip() and not l.startswith("#")])

        # Remove matching lines and their "Added by Friday" comments
        filtered = []
        skip_next = False
        for line in lines:
            if skip_next:
                skip_next = False
                continue
            if arg.lower() in line.lower() and not line.startswith("#"):
                # Also remove preceding Friday comment
                if filtered and filtered[-1].strip() == "# Added by Friday":
                    filtered.pop()
                continue
            if line.strip() == "# Added by Friday":
                # Check if next line matches
                skip_next = False  # will be handled when we get to the next line
            filtered.append(line)

        new_count = len([l for l in filtered if l.strip() and not l.startswith("#")])
        removed = original_count - new_count

        if removed == 0:
            return f"No jobs matching '{arg}' found."

        result = _set_crontab("\n".join(filtered) + "\n")
        return f"Removed {removed} job(s) matching '{arg}'.\n{result}"

    elif cmd == "explain":
        if not arg:
            return "Usage: explain <schedule>\nExample: explain 0 9 * * 1-5"
        return _explain_schedule(arg)

    else:
        return (
            "Usage: cron <action>\n"
            "  list              — show all scheduled jobs\n"
            "  add <when> <cmd>  — schedule a new job\n"
            "  remove <pattern>  — remove jobs matching pattern\n"
            "  explain <sched>   — explain a cron schedule\n"
            "\nShortcuts for 'add': every minute, every hour, every morning, "
            "every night, every monday, every weekday, every weekend, every reboot"
        )
