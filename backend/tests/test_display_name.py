import re

from fastapi.testclient import TestClient

from backend.app.data.seed import generate_synthetic_agents
from backend.app.main import app
from backend.app.service import world_service

client = TestClient(app)


def setup_function():
    world_service.reset()


def test_seed_generates_synthetic_chinese_display_names():
    agents = generate_synthetic_agents(80)
    names = [agent.display_name for agent in agents]
    assert len(names) == 80
    assert len(set(names)) == 80, "display_name 必须唯一"
    assert all(re.fullmatch(r"模拟人员\d{3}", name) for name in names), "全部为 Synthetic 中文名，不得使用真实姓名"
    assert names[0] == "模拟人员001"
    assert names[49] == "模拟人员050"
    assert names[79] == "模拟人员080"


def test_display_name_does_not_change_agent_ids():
    agents = {agent.id: agent for agent in generate_synthetic_agents(80)}
    assert set(agents) == set(world_service.state.agents), "Agent id 与主键关系保持不变"
    assert agents["agent_A"].display_name == "模拟人员001"
    assert agents["agent_50"].display_name == "模拟人员050"
    assert agents["agent_80"].display_name == "模拟人员080"


def test_world_state_api_returns_display_name():
    state = client.get("/api/world/state").json()
    agent = state["agents"]["agent_50"]
    assert agent["id"] == "agent_50"
    assert agent["display_name"] == "模拟人员050"
    assert all(item["display_name"] for item in state["agents"].values())
