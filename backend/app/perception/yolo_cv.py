from ..ontology.models import Event
from .base import CVEventProvider


class RealCVProvider(CVEventProvider):
    def detect(self, event_name: str, subject_id: str | None = None) -> Event:
        raise NotImplementedError("MVP 仅启用 MockCVProvider；真实 YOLO 作为可插拔扩展。")

