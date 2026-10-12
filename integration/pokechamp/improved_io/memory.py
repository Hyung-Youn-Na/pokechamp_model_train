"""Battle-local summary identity and event-reference validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADINGS = (
    "Identity and Coverage",
    "Current Position",
    "Team and Revealed Opponent Information",
    "Pending Effects and Restrictions",
    "Relevant Event Ledger",
    "Hypotheses and Current Options",
    "Corrections and Unresolved Conflicts",
)


def validate_summary(text, *, battle_id, actor_id, event_ids):
    if not isinstance(text, str) or not re.fullmatch(r"<summary>\s*.*\s*</summary>", text, re.S):
        raise ValueError("expected exactly one summary block")
    if text.count("<summary>") != 1 or text.count("</summary>") != 1:
        raise ValueError("multiple summary blocks")
    if any(f"## {heading}" not in text for heading in HEADINGS):
        raise ValueError("summary section missing")
    # Runtime supplies machine-checkable identity and reference syntax in the task
    # input. Free prose cannot silently select a different actor or future event.
    identities = re.findall(r"^battle_id: (.+)$", text, re.M)
    actors = re.findall(r"^actor_id: (.+)$", text, re.M)
    if identities != [battle_id] or actors != [actor_id]:
        raise ValueError("foreign or missing summary identity")
    references = {int(x) for x in re.findall(r"\[event:(\d+)\]", text)}
    if not references or not references <= set(event_ids):
        raise ValueError("missing or unavailable summary event references")
    if re.search(r'"(?:move|switch|terastallize)"\s*:', text):
        raise ValueError("action JSON in summary")
    return text


@dataclass
class BattleMemory:
    battle_id: str
    actor_id: str
    enabled: bool
    decisions: int = 0
    summarized_decisions: int = 0
    summaries: list = field(default_factory=list)
    archive: list = field(default_factory=list)
    consolidated: str | None = None

    def due(self):
        return self.enabled and self.decisions - self.summarized_decisions >= 10

    def accept(self, text, event_ids, *, rollup=False):
        validate_summary(
            text, battle_id=self.battle_id, actor_id=self.actor_id, event_ids=event_ids
        )
        if rollup and len(self.summaries) != 3:
            raise ValueError("rollup requires three summaries")
        if not rollup and not self.due():
            raise ValueError("summary before ten completed decisions")
        self.archive.append(
            {
                "role": "summary_rollup" if rollup else "summary",
                "text": text,
                "event_ids": sorted(event_ids),
            }
        )
        if rollup:
            self.consolidated = text
            self.summaries = []
        else:
            self.summaries.append(text)
            self.summarized_decisions = self.decisions


def summary_context(
    value, source_events, *, source_event_ids=None, previous=None, observed_protocol=None
):
    """The same input builder serves live summaries and offline first-boundary replay."""
    from .protocol import annotate

    identity = value["identity"]
    context = dict(
        condition_id=value.get("condition_id", "C"),
        identity=identity,
        current_observation=value["current_observation"],
        source_events=source_events,
        source_event_ids=source_event_ids
        if source_event_ids is not None
        else [e["event_seq"] for e in source_events],
        previous_summary=previous,
        output_identity_format="Inside Identity and Coverage write separate lines "
        f"battle_id: {identity['battle_id']}\nactor_id: {identity['actor_id']}\n"
        "Cite supplied event numbers as [event:123].",
    )
    # Carry occurrence turns and preceding observed HP across a summary boundary.
    # Only the current interval's rows are emitted; the full prefix is never added
    # to the model's raw-event window.
    annotation_source = dict(context, source_events=observed_protocol or source_events)
    context["harness_annotations"] = annotate(annotation_source)
    selected = {e["event_seq"] for e in source_events}
    context["harness_annotations"]["event_annotations"] = [
        row
        for row in context["harness_annotations"]["event_annotations"]
        if row["ref"]["event"] in selected
    ]
    return context


def summary_window(context, previous_cutoff, *, previous=None):
    """Build subsequent replay summaries with exactly the live actor's event window."""
    return summary_context(
        context,
        [e for e in context["source_events"] if e["event_seq"] >= previous_cutoff],
        source_event_ids=context["source_event_ids"],
        previous=previous,
        observed_protocol=context["source_events"],
    )
