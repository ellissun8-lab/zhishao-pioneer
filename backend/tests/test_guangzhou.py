"""P1-1 / P1-2 专项测试：广州演示场景坐标范围与 school_zone_001 全仓一致性。"""

from pathlib import Path

from backend.app.data.seed import create_demo_state, position_in_guangzhou
from backend.app.service import world_service
from backend.app.simulation.runtime import SyntheticAgentRuntime
from backend.app.world.event_bus import EventBus

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIR_NAMES = {"node_modules", ".git", "dist", "__pycache__", ".pytest_cache", ".git-source-empty", ".venv"}
# 历史文档不计入一致性扫描：两份任务书（智哨先锋--*.md）与 Codex 验证报告（按规则不得修改）；本测试文件自身包含被扫描的字面量
def _is_skipped_name(name: str) -> bool:
    return (
        name.startswith("智哨先锋")
        or "codex-validation-report" in name
        or name in {"test_guangzhou.py"}
    )
SCANNABLE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".css", ".html", ".yml", ".ini", ".example", ".txt"}


def test_seed_agents_destinations_and_history_within_guangzhou():
    state = create_demo_state(80)
    for agent in state.agents.values():
        assert position_in_guangzhou(agent.position), f"{agent.id} position out of Guangzhou: {agent.position}"
        assert position_in_guangzhou(agent.destination), f"{agent.id} destination out of Guangzhou: {agent.destination}"
        for point in agent.history:
            assert position_in_guangzhou(point), f"{agent.id} history out of Guangzhou: {point}"


def test_seed_places_and_zones_within_guangzhou():
    state = create_demo_state(80)
    for place in state.places.values():
        assert position_in_guangzhou(place.position), place.id
    for zone in state.zones.values():
        assert position_in_guangzhou(zone.center), zone.id


def test_advance_demo_positions_within_guangzhou():
    world_service.reset()
    for _ in range(4):
        world_service.advance_demo()
    for agent in world_service.state.agents.values():
        assert position_in_guangzhou(agent.position), f"{agent.id} out of Guangzhou after demo step"


def test_runtime_keeps_all_agents_within_guangzhou():
    state = create_demo_state(80)
    bus = EventBus(state)
    runtime = SyntheticAgentRuntime(seed=42)
    for _ in range(60):
        runtime.tick(state, bus.publish, dt_seconds=60)
    for agent in state.agents.values():
        assert position_in_guangzhou(agent.position), f"{agent.id} out of Guangzhou after runtime ticks"
        if agent.destination is not None:
            assert position_in_guangzhou(agent.destination)


def _project_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCANNABLE_SUFFIXES:
            continue
        if SKIP_DIR_NAMES & set(path.parts):
            continue
        if _is_skipped_name(path.name):
            continue
        yield path


def test_zone_id_is_school_zone_001_everywhere():
    state = create_demo_state()
    assert set(state.zones) == {"school_zone_001"}
    offenders = []
    for path in _project_text_files(PROJECT_ROOT):
        if "zone_school_001" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == [], f"legacy zone id remains in: {offenders}"
