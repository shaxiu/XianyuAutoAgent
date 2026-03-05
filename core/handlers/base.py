from typing import List

from core.models import Action, Event


class EventHandler:
    name = "base"

    def handle(self, event: Event) -> List[Action]:
        return []

