
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from core.engine import Engine
from rich.console import Console

console = Console()
engine = Engine()
print(f"DEBUG: Config path: {engine.config.config_path}")
data = engine.config.load()
print(f"DEBUG: Loaded data keys: {list(data.keys())}")
print(f"DEBUG: Resources count: {len(engine.config.resources)}")

engine.state.load()
diff = engine.state.diff(engine.config.resources)
print(f"DEBUG: Diff create count: {len(diff['create'])}")

from core.graph import DependencyGraph
graph = DependencyGraph.from_resources(engine.config.resources)
order = graph.topological_sort()
print(f"DEBUG: Topological order: {order}")

plan = engine.plan()
print(f"DEBUG: Plan actions count: {len(plan.actions)}")
plan.display(console)
