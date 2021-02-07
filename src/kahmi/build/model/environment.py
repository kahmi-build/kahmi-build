
import typing as t

from .build_graph import BuildGraph
from .project import Project
from .state_tracker import NoStateTracker, StateTracker


class Environment:

  def __init__(self, state_tracker: t.Optional[StateTracker] = None):
    self.state_tracker = state_tracker or NoStateTracker()
    self.graph = BuildGraph()
    self.root_project: t.Optional[Project] = None
