from __future__ import annotations

from models.decision import ActionType

from .conversation_intervention import ConversationIntervention
from .de_escalation_intervention import DeEscalationIntervention
from .reminiscence_intervention import ReminiscenceIntervention
from .fall_intervention import FallIntervention


_INTERVENTIONS = {
    "conversation": ConversationIntervention(),
    "de_escalation": DeEscalationIntervention(),
    "reminiscence": ReminiscenceIntervention(),
    "fall_protocol": FallIntervention(),
}


def get_intervention(action: ActionType | str):
    if hasattr(action, "value"):
        key = str(action.value).strip().lower()
    else:
        key = str(action).strip().lower()
    return _INTERVENTIONS.get(key)