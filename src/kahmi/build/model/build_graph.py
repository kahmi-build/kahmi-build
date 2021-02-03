
import typing as t

import networkx  # type: ignore
import networkx.algorithms.dag  # type: ignore

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
    Adds all default tasks of a project to the graph.
    """

    for task in project.iter_all_tasks():
      if task.default:
        self.add_task(task)

  def add_task(self, task: Task) -> None:
    """
    Adds a task and all its dependencies and finalizers to the build graph.
    """

    if task in self._seen:
      return

    self._graph.add_node(task)

    for dependency in task.compute_all_dependencies():
      self.add_task(dependency)
      self._graph.add_edge(dependency, task)

    for finalizer in task.finalizers:
      self.add_task(finalizer)
      self._graph.add_edge(task, finalizer)

  def add_tasks(self, tasks: t.Iterable[Task]) -> None:
    for task in tasks:
      self.add_task(task)

  def topological_order(self) -> t.Iterator[Task]:
    """
    Returns the topological order of the graph, i.e. in the order in which tasks need to be
    executed.
    """

    return networkx.algorithms.dag.topological_sort(self._graph)
