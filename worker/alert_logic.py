from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class AlertState:
    uid: str
    title: str
    threshold: float | None
    first_trigger_time: datetime | None = None
    last_value: float | None = None
    action_written: bool = False  # Track if action was already written for this alert instance

    def update(self, value: float, now: datetime, duration_required: int) -> bool:
        """Update with new value; return True if duration threshold reached."""
        self.last_value = value
        if self.first_trigger_time is None:
            self.first_trigger_time = now
            print(f"[DURATION] Alert '{self.title}' first trigger at {now.strftime('%H:%M:%S')}")
            return False
        sustained = (now - self.first_trigger_time).total_seconds()
        print(f"[DURATION] Alert '{self.title}' sustained for {sustained:.1f}s (need {duration_required}s)")
        return sustained >= duration_required

    def reset(self):
        self.first_trigger_time = None
        self.last_value = None
        self.action_written = False  # Reset action flag when alert clears

class AlertDurationManager:
    def __init__(self, duration_required: int):
        self.duration_required = duration_required
        self.states: dict[str, AlertState] = {}

    def process(self, alert_uid: str, title: str, threshold: float | None, current_value: float, status: str) -> bool:
        """Return True if sustained duration exceeded and action should run.
        status: firing | normal
        """
        now = datetime.now(timezone.utc)
        if status != 'firing':
            # reset state if recovered
            if alert_uid in self.states:
                self.states[alert_uid].reset()
            return False
        state = self.states.get(alert_uid)
        if state is None:
            state = AlertState(alert_uid, title, threshold)
            self.states[alert_uid] = state
        return state.update(current_value, now, self.duration_required)
    
    def get_alert_state(self, alert_uid: str) -> AlertState | None:
        """Get the current state of an alert."""
        return self.states.get(alert_uid)
    
    def mark_action_written(self, alert_uid: str):
        """Mark that an action has been written for this alert."""
        if alert_uid in self.states:
            self.states[alert_uid].action_written = True
