import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.data.seed import generate_synthetic_agents


def main() -> None:
    target = Path(__file__).parents[1] / "data" / "synthetic" / "agents.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps([agent.model_dump(mode="json") for agent in generate_synthetic_agents()], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated 80 synthetic agents: {target}")


if __name__ == "__main__":
    main()
