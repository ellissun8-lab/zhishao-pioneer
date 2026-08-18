from .models import Relation

# 统一城市本体关系（与 backend/app/ontology/schema.json 保持一致）
RELATION_TYPES = {
    "located_at": "Person -> located_at -> Place（主体所在地点）",
    "enters": "Person -> enters -> Zone（主体进入敏感区）",
    "gathers_with": "Person -> gathers_with -> Person（主体间聚集关系）",
    "occurs_at": "Event -> occurs_at -> Place（事件发生地点）",
    "changes": "Event -> changes -> WorldState（事件对世界状态的影响）",
    "affects": "Action -> affects -> Event（干预动作作用的事件）",
}


def make_relation(subject_id: str, predicate: str, object_id: str) -> Relation:
    if predicate not in RELATION_TYPES:
        raise ValueError(f"Unsupported relation: {predicate}")
    return Relation(subject_id=subject_id, predicate=predicate, object_id=object_id)
