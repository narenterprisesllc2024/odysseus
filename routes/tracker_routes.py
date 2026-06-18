"""Tracker routes — reads/writes the 4-tier execution tracker markdown file.

Source of truth: /opt/aionui/SHARED_MEMORY/tracker_active_execution.md

Parses sections by header emoji prefix; daily-rhythm items auto-uncheck at
midnight (server-local) via a sidecar JSON of last-check dates.
"""

import json
import logging
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.middleware import require_admin

logger = logging.getLogger(__name__)

TRACKER_PATH = Path("/opt/aionui/SHARED_MEMORY/tracker_active_execution.md")
DAILY_STATE_PATH = Path("/opt/aionui/SHARED_MEMORY/tracker_daily_state.json")
ARCHIVE_MARKER = "## 📚 ARCHIVE"

SECTIONS = [
    {"id": "north_star", "emoji": "🌟", "title": "North Star", "subtitle": "multi-year horizon"},
    {"id": "daily_rhythm", "emoji": "🔁", "title": "Daily Rhythm", "subtitle": "resets at midnight"},
    {"id": "today", "emoji": "✅", "title": "Today", "subtitle": "the 3 highest-leverage right now"},
    {"id": "this_week", "emoji": "⚡", "title": "This Week", "subtitle": "next-up — auto-promotes to today"},
    {"id": "this_month", "emoji": "🎯", "title": "This Month", "subtitle": "30-day priorities"},
]

_LOCK = threading.Lock()


def _load_daily_state() -> Dict[str, str]:
    if not DAILY_STATE_PATH.exists():
        return {}
    try:
        return json.loads(DAILY_STATE_PATH.read_text())
    except Exception:
        return {}


def _save_daily_state(state: Dict[str, str]) -> None:
    DAILY_STATE_PATH.write_text(json.dumps(state, indent=2))


def _read_active_portion() -> str:
    """Return the file content above the archive marker."""
    full = TRACKER_PATH.read_text()
    idx = full.find(ARCHIVE_MARKER)
    return full if idx == -1 else full[:idx]


def _read_full() -> str:
    return TRACKER_PATH.read_text()


def _section_for_header(line: str) -> Optional[Dict[str, str]]:
    """Match a markdown H2 to one of our known sections by emoji."""
    if not line.startswith("## "):
        return None
    for sec in SECTIONS:
        if sec["emoji"] in line:
            return sec
    return None


_CHECKBOX_RE = re.compile(r"^- \[( |x|X)\] (.+)$")


def _parse_tracker() -> Dict[str, Any]:
    """Walk the active portion, group checkboxes by section."""
    text = _read_active_portion()
    daily_state = _load_daily_state()
    today_iso = date.today().isoformat()

    sections: Dict[str, Dict[str, Any]] = {
        sec["id"]: {**sec, "items": []} for sec in SECTIONS
    }
    current = None
    for raw_line in text.splitlines():
        sec = _section_for_header(raw_line)
        if sec is not None:
            current = sec["id"]
            continue
        if current is None:
            continue
        m = _CHECKBOX_RE.match(raw_line.rstrip())
        if not m:
            continue
        checked = m.group(1).lower() == "x"
        label = m.group(2)
        item_id = f"{current}::{label}"
        item = {"id": item_id, "label": label, "checked": checked}
        if current == "daily_rhythm":
            last = daily_state.get(item_id)
            item["checked"] = (last == today_iso)
            item["last_checked"] = last
        sections[current]["items"].append(item)

    return {
        "updated": datetime.utcnow().isoformat() + "Z",
        "today": today_iso,
        "sections": [sections[sec["id"]] for sec in SECTIONS],
    }


def _toggle_line(item_label: str, section_id: str, want_checked: bool) -> bool:
    """Rewrite the tracker file flipping a single checkbox. Returns True if changed."""
    full = _read_full()
    active_end = full.find(ARCHIVE_MARKER)
    active = full if active_end == -1 else full[:active_end]
    archive = "" if active_end == -1 else full[active_end:]

    lines = active.splitlines()
    target_section_emoji = next(
        (sec["emoji"] for sec in SECTIONS if sec["id"] == section_id), None
    )
    if target_section_emoji is None:
        return False

    in_target_section = False
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_target_section = target_section_emoji in line
            continue
        if not in_target_section:
            continue
        m = _CHECKBOX_RE.match(line.rstrip())
        if not m:
            continue
        if m.group(2) != item_label:
            continue
        currently_checked = m.group(1).lower() == "x"
        if currently_checked == want_checked:
            return False
        new_box = "[x]" if want_checked else "[ ]"
        lines[i] = f"- {new_box} {item_label}"
        changed = True
        break

    if not changed:
        return False
    new_active = "\n".join(lines)
    if archive:
        # preserve the blank line before the archive header
        if not new_active.endswith("\n"):
            new_active += "\n"
    TRACKER_PATH.write_text(new_active + archive)
    return True


def _toggle_today_with_promote(item_label: str, want_checked: bool):
    """Flip a Today checkbox; if checking, also promote first unchecked This Week
    item up into Today (it moves from Week to Today). Returns (changed, promoted_label_or_None).
    Single file rewrite — atomic under the route's lock.
    """
    full = _read_full()
    active_end = full.find(ARCHIVE_MARKER)
    active = full if active_end == -1 else full[:active_end]
    archive = "" if active_end == -1 else full[active_end:]
    lines = active.splitlines()

    today_emoji = "✅"
    week_emoji = "⚡"

    # Pass 1 — flip the Today item + remember the last Today checkbox index
    in_today = False
    today_last_checkbox_idx = -1
    today_changed = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_today = today_emoji in line
            continue
        if not in_today:
            continue
        m = _CHECKBOX_RE.match(line.rstrip())
        if not m:
            continue
        today_last_checkbox_idx = i
        if m.group(2) == item_label:
            currently = m.group(1).lower() == "x"
            if currently == want_checked:
                continue
            new_box = "[x]" if want_checked else "[ ]"
            lines[i] = f"- {new_box} {item_label}"
            today_changed = True

    if not today_changed:
        return False, None

    # Pass 2 — if checking, promote first unchecked Week item into Today
    promoted = None
    if want_checked:
        in_week = False
        for i, line in enumerate(lines):
            if line.startswith("## "):
                in_week = week_emoji in line
                continue
            if not in_week:
                continue
            m = _CHECKBOX_RE.match(line.rstrip())
            if not m or m.group(1).lower() == "x":
                continue
            promoted = m.group(2)
            # Today is ABOVE Week in file, so popping from Week never shifts today_last_checkbox_idx
            lines.pop(i)
            lines.insert(today_last_checkbox_idx + 1, f"- [ ] {promoted}")
            break

    new_active = "\n".join(lines)
    if archive and not new_active.endswith("\n"):
        new_active += "\n"
    TRACKER_PATH.write_text(new_active + archive)
    return True, promoted


class ToggleBody(BaseModel):
    section_id: str
    item_label: str
    checked: bool


def setup_tracker_routes() -> APIRouter:
    router = APIRouter(tags=["tracker"])

    @router.get("/api/tracker/state")
    async def get_state(request: Request) -> Dict[str, Any]:
        require_admin(request)
        with _LOCK:
            try:
                return _parse_tracker()
            except Exception as e:
                logger.exception("tracker parse failed")
                raise HTTPException(500, f"tracker parse failed: {e}")

    @router.post("/api/tracker/toggle")
    async def toggle(request: Request, body: ToggleBody) -> Dict[str, Any]:
        require_admin(request)
        with _LOCK:
            try:
                if body.section_id == "daily_rhythm":
                    state = _load_daily_state()
                    item_id = f"{body.section_id}::{body.item_label}"
                    if body.checked:
                        state[item_id] = date.today().isoformat()
                    else:
                        state.pop(item_id, None)
                    _save_daily_state(state)
                    return {"ok": True, "daily_rhythm": True, "checked": body.checked}
                if body.section_id == "today" and body.checked:
                    changed, promoted = _toggle_today_with_promote(body.item_label, True)
                    return {"ok": True, "changed": changed, "checked": True, "promoted": promoted}
                changed = _toggle_line(body.item_label, body.section_id, body.checked)
                return {"ok": True, "changed": changed, "checked": body.checked}
            except Exception as e:
                logger.exception("tracker toggle failed")
                raise HTTPException(500, f"tracker toggle failed: {e}")

    @router.post("/api/tracker/add")
    async def add_item(request: Request, body: ToggleBody) -> Dict[str, Any]:
        """Append a new unchecked item to a section."""
        require_admin(request)
        with _LOCK:
            try:
                full = _read_full()
                active_end = full.find(ARCHIVE_MARKER)
                active = full if active_end == -1 else full[:active_end]
                archive = "" if active_end == -1 else full[active_end:]
                emoji = next(
                    (sec["emoji"] for sec in SECTIONS if sec["id"] == body.section_id), None
                )
                if emoji is None:
                    raise HTTPException(400, "unknown section_id")
                lines = active.splitlines()
                insert_after = -1
                in_target = False
                last_checkbox_idx = -1
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        if in_target:
                            insert_after = last_checkbox_idx if last_checkbox_idx != -1 else i - 1
                            break
                        in_target = emoji in line
                        continue
                    if in_target and _CHECKBOX_RE.match(line.rstrip()):
                        last_checkbox_idx = i
                if in_target and insert_after == -1:
                    insert_after = last_checkbox_idx if last_checkbox_idx != -1 else len(lines) - 1
                if insert_after == -1:
                    raise HTTPException(404, "section not found in file")
                lines.insert(insert_after + 1, f"- [ ] {body.item_label}")
                new_active = "\n".join(lines)
                if archive and not new_active.endswith("\n"):
                    new_active += "\n"
                TRACKER_PATH.write_text(new_active + archive)
                return {"ok": True, "added": body.item_label}
            except HTTPException:
                raise
            except Exception as e:
                logger.exception("tracker add failed")
                raise HTTPException(500, f"tracker add failed: {e}")

    return router
