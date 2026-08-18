"""公开城市数据导入扩展点；MVP 使用 data/demo 中可追溯的演示样本。"""

from pathlib import Path


if __name__ == "__main__":
    data_dir = Path(__file__).parents[1] / "data" / "public"
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Public-data staging directory ready: {data_dir}")

