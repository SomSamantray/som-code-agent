"""
Session History — persist, resume, and fork coding sessions.

Sessions are stored as JSON files in ~/.som/sessions/.
Each session records: task, model, turns, tool calls, results, duration.
"""

import json
import os
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionRecord:
    """A persisted session record."""
    session_id: str
    task: str
    model: str
    workspace: str
    started_at: str
    ended_at: Optional[str] = None
    turn_count: int = 0
    tool_call_count: int = 0
    total_tokens: dict = field(default_factory=dict)
    success: bool = False
    final_response: str = ""
    error: Optional[str] = None
    tags: list[str] = field(default_factory=list)


class SessionManager:
    """
    Manages session persistence, listing, resuming, and forking.

    Sessions directory: ~/.som/sessions/
    """

    def __init__(self, sessions_dir: str = None):
        self.sessions_dir = Path(sessions_dir or os.path.expanduser("~/.som/sessions"))
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[SessionRecord] = None

    def start_session(self, task: str, model: str, workspace: str) -> SessionRecord:
        """Start a new session and return the record."""
        session_id = str(uuid.uuid4())[:12]
        record = SessionRecord(
            session_id=session_id,
            task=task,
            model=model,
            workspace=workspace,
            started_at=time.ctime(),
        )
        self._current_session = record
        self._save(record)
        return record

    def end_session(self, success: bool = False, final_response: str = "", error: str = None):
        """Mark the current session as ended."""
        if not self._current_session:
            return
        
        self._current_session.ended_at = time.ctime()
        self._current_session.success = success
        self._current_session.final_response = final_response[:500]
        self._current_session.error = error
        self._save(self._current_session)

    def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        """List recent sessions, newest first."""
        records = []
        for fpath in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fpath.read_text())
                records.append(SessionRecord(**data))
            except Exception:
                continue
            if len(records) >= limit:
                break
        return records

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session by ID."""
        fpath = self.sessions_dir / f"{session_id}.json"
        if not fpath.exists():
            return None
        try:
            data = json.loads(fpath.read_text())
            return SessionRecord(**data)
        except Exception:
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session record."""
        fpath = self.sessions_dir / f"{session_id}.json"
        if fpath.exists():
            fpath.unlink()
            return True
        return False

    def _save(self, record: SessionRecord):
        """Persist a session record to disk."""
        fpath = self.sessions_dir / f"{record.session_id}.json"
        fpath.write_text(json.dumps(record.__dict__, indent=2))

    def format_session_list(self, sessions: list[SessionRecord] = None) -> str:
        """Format sessions for display."""
        sessions = sessions or self.list_sessions()
        if not sessions:
            return "No saved sessions."
        
        lines = ["Recent sessions:"]
        for s in sessions:
            status = "✅" if s.success else ("❌" if s.error else "⏳")
            lines.append(
                f"  {status} [{s.session_id}] {s.task[:60]}"
                f" — {s.model} — {s.turn_count}t — {s.started_at[:16]}"
            )
        return "\n".join(lines)
