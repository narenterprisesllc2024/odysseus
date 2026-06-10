#!/bin/bash
# apply-persona.sh — Install Sovi F.R.I.D.A.Y. persona into Odysseus
# Idempotent: safe to run multiple times.
set -euo pipefail

PROJECT="/opt/aionui/projects/odysseus-sovi"
DB="${PROJECT}/data/app.db"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Sovi F.R.I.D.A.Y. Persona Installer ==="

# 1. Copy new files
echo "[1/4] Copying persona.md and persona.py..."
cp -v "${BUILD_DIR}/data/persona.md" "${PROJECT}/data/persona.md"
cp -v "${BUILD_DIR}/src/persona.py" "${PROJECT}/src/persona.py"

# 2. Patch agent_loop.py — inject persona into _build_system_prompt
AGENT_LOOP="${PROJECT}/src/agent_loop.py"
MARKER="# --- Sovi persona injection ---"
if grep -qF "$MARKER" "$AGENT_LOOP" 2>/dev/null; then
    echo "[2/4] agent_loop.py already patched — skipping"
else
    echo "[2/4] Patching agent_loop.py..."
    # Insert persona injection after the date/time block (line with "agent_prompt = current_datetime_prompt")
    # We inject right after the `except Exception: pass` that follows the date/time block
    python3 - "$AGENT_LOOP" "$MARKER" <<'PYEOF'
import sys, re

filepath = sys.argv[1]
marker = sys.argv[2]

with open(filepath, 'r') as f:
    content = f.read()

# Find the date/time injection block end — the pattern:
#     except Exception:
#         pass
#
#     # Document context...
# We inject our persona block between "pass" and "# Document context"
target = '''    except Exception:
        pass

    # Document context is kept as a SEPARATE message'''

replacement = '''    except Exception:
        pass

    ''' + marker + '''
    try:
        from src.persona import load_persona
        _persona_text = load_persona()
        if _persona_text:
            agent_prompt = _persona_text + "\\n\\n" + agent_prompt
    except Exception:
        pass

    # Document context is kept as a SEPARATE message'''

if target not in content:
    print(f"WARNING: Could not find injection point in {filepath}", file=sys.stderr)
    print("  The file may have been modified. Manual patch needed.", file=sys.stderr)
    sys.exit(1)

content = content.replace(target, replacement, 1)
with open(filepath, 'w') as f:
    f.write(content)
print(f"  Patched {filepath}")
PYEOF
fi

# 3. Patch chat_processor.py — inject persona into build_context_preface
CHAT_PROC="${PROJECT}/src/chat_processor.py"
if grep -qF "$MARKER" "$CHAT_PROC" 2>/dev/null; then
    echo "[3/4] chat_processor.py already patched — skipping"
else
    echo "[3/4] Patching chat_processor.py..."
    python3 - "$CHAT_PROC" "$MARKER" <<'PYEOF'
import sys

filepath = sys.argv[1]
marker = sys.argv[2]

with open(filepath, 'r') as f:
    content = f.read()

# Find the preset system prompt injection block:
#         # Add preset system prompt if specified
#         if preset_system_prompt:
target = '''        # Add preset system prompt if specified
        if preset_system_prompt:
            preface.append({
                "role": "system",
                "content": preset_system_prompt
            })'''

replacement = '''        ''' + marker + '''
        try:
            from src.persona import load_persona
            _persona_text = load_persona()
            if _persona_text:
                preface.append({
                    "role": "system",
                    "content": _persona_text,
                })
        except Exception:
            pass

        # Add preset system prompt if specified
        if preset_system_prompt:
            preface.append({
                "role": "system",
                "content": preset_system_prompt
            })'''

if target not in content:
    print(f"WARNING: Could not find injection point in {filepath}", file=sys.stderr)
    print("  The file may have been modified. Manual patch needed.", file=sys.stderr)
    sys.exit(1)

content = content.replace(target, replacement, 1)
with open(filepath, 'w') as f:
    f.write(content)
print(f"  Patched {filepath}")
PYEOF
fi

# 4. Update CrewMember personality in database
echo "[4/4] Updating CrewMember personality in database..."
python3 - "$DB" "${BUILD_DIR}/data/persona.md" <<'PYEOF'
import sqlite3, sys

db_path = sys.argv[1]
persona_path = sys.argv[2]

with open(persona_path, 'r') as f:
    persona = f.read().strip()

# Build the full personality: Sovi persona + operational rules
personality = persona + """

## Operational rules (assistant mode)

CORE RULE: You MUST use your tools to take action — do not describe what you would do. Never say 'I would check your calendar' — actually call manage_calendar. Never say 'I can look that up' — actually call web_search or search_chats. If you have a tool for it, use it. No hypotheticals, no promises, only actions and results.

CONTEXT GATHERING (before any response involving a specific person):
1. resolve_contact if you only have a name and need their email
2. search_chats for recent conversations mentioning them or their topic
3. manage_memory to check stored facts about them
Skip steps you already have answers for. Don't search for the user themselves.

EMAIL HANDLING:
- If a document is open in the editor, that IS the email. Use update_document to write the reply.
- BEFORE drafting any reply: gather context about the sender and topic.
- When an email mentions a date/meeting: check calendar for conflicts, add if clear.
- Skip automated/marketing emails in check-ins. Only surface human-sent, actionable ones.
- Never duplicate information the user already saw in a previous check-in.

SELF-IMPROVEMENT — use manage_memory constantly:
- When Nate corrects you, IMMEDIATELY store the correction as a memory.
- After every check-in or task, store new facts you learned.
- Before responding about a person or topic, search_chats and manage_memory FIRST.
- If something failed or you got corrected, store WHY so you never repeat it.

AUTONOMY RULES:
- Auto-add calendar events from clear meeting invitations (mention what you added)
- Auto-draft email replies (cached for when user clicks Reply)
- NEVER send emails without explicit user instruction
- NEVER delete anything without explicit instruction
- If uncertain, ask rather than guess"""

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute(
    "UPDATE crew_members SET personality = ?, name = ? WHERE is_default_assistant = 1",
    (personality, "Sovi"),
)
rows = cur.rowcount
conn.commit()
conn.close()

if rows:
    print(f"  Updated {rows} CrewMember row(s) — name='Sovi', personality set to F.R.I.D.A.Y. persona")
else:
    print("  WARNING: No default assistant found in crew_members table", file=sys.stderr)
PYEOF

echo ""
echo "=== Done. Restart Odysseus to pick up changes: ==="
echo "  cd ${PROJECT} && docker compose restart"
