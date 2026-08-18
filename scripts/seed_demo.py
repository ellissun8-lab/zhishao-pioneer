import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.data.seed import create_demo_state


if __name__ == "__main__":
    state = create_demo_state()
    print(f"Seeded in-memory demo: {len(state.agents)} synthetic agents, {len(state.zones)} sensitive zone")
