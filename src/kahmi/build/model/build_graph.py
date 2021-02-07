
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
    self._selected: t.Set[Task] = set()

  def add_project(self, project: Project) -> None:
    """
    Adds all default tasks of a project to the graph.
    """

    self.add_tasks(project.iter_all_tasks())

  def add_task(self, task: Task) -> None:
    """
    Adds a task and all its dependencies and finalizers to the build graph.
    """

    if task in self._seen:
      return

    self._seen.add(task)
    self._graph.add_node(task)

    for dependency in task.compute_all_dependencies():
      self.add_task(dependency)
      self._graph.add_edge(dependency, task)

    for finalizer in task.finalizers:
      self.add_task(finalizer)
      self._graph.add_edge(task, finalizer)

  def add_tasks(self, tasks: t.Iterable[Task]) -> None:
    """
    Add multiple tasks to the graph.
    """

    for task in tasks:
      self.add_task(task)

  def select(self, task: Task) -> None:
    """
    Mark a task as selected.
    """

    self._selected.add(task)

  def select_defaults(self) -> None:
    """
    Select all tasks that are default tasks.
    """

    for task in self.tasks():
      if task.default:
        self.select(task)

  def is_selected(self, task: Task) -> bool:
    return task in self._selected

  def tasks(self) -> t.Iterator[Task]:
    return iter(self._seen)

  def selected_tasks(self) -> t.Iterator[Task]:
    return iter(self._selected)

  def tasks_in_order(self) -> t.Iterator[Task]:
    """
    Returns the topological order of the graph, i.e. in the order in which tasks need to be
    executed.
    """

    subgraph = BuildGraph()
    for task in self.selected_tasks():
      subgraph.add_task(task)

    return networkx.algorithms.dag.topological_sort(subgraph._graph)


class GraphState:

  pass
