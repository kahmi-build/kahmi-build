
import typing as t

import networkx
import networkx.algorithms.dag

from .project import Project
from .task import Task


class BuildGraph:
  """
  Represents the build graph that is built after all projects are evaluated from which the order
  of tasks is derived.
  """

  def __init__(self):
    self._graph = networkx.DiGraph()
    self._seen: t.Set[Task] = set()

  def add_project(self, project: Project) -> None:
    """
    Adds all tasks of a project.
    """

    for task in project.iter_tasks():
      self.add_task(task)

  def add_task(self, task: Task) -> None:
    """
    Adds a task and all its dependencies and finalizers to the build graph.
    """

    if task in self._seen:
      return

    self._graph.add_node(task)

    for dependency in task.dependencies:
      self.add_task(dependency)
      self._graph.add_edge(dependency, task)

    for finalizer in task.finalizers:
      self.add_task(finalizer)
      self._graph.add_edge(task, finalizer)

  def topological_order(self) -> t.Iterator[Task]:
    """
    Returns the topological order of the graph, i.e. in the order in which tasks need to be
    executed.
    """

    return networkx.algorithms.dag.topological_sort(self._graph)
