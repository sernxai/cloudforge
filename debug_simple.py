
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from core.engine import Engine

engine = Engine()
engine.config.load()
engine.state.load()
plan = engine.plan()

print(f"PLAN ACTIONS: {len(plan.actions)}")
for action in plan.actions:
    print(f"ACTION: {action.action} {action.resource_name} ({action.resource_type})")
