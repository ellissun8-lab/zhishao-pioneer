from abc import ABC, abstractmethod

from ..ontology.models import Event


class CVEventProvider(ABC):
    @abstractmethod
    def detect(self, event_name: str, subject_id: str | None = None) -> Event:
        """将感知结果转换为统一 Ontology Event。"""

