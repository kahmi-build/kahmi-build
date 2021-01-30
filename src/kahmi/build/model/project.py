
import os
import typing as t
import weakref
from pathlib import Path

from kahmi.dsl import Configurable, NameProvider, run_file
from nr.functional import flatmap

from .task import Task
from .task_container import TaskContainer
from .plugin import apply_plugin

T_Task = t.TypeVar('T_Task', bound=Task)


class Project(Configurable, NameProvider):

  DEFAULT_BUILD_DIRECTORY_NAME = '.build'

  def __init__(self, parent: t.Optional['Project'], name: str, directory: Path) -> None:
    assert name, "project name cannot be empty"
    assert isinstance(directory, Path), "directory must be Path instance"
    self._parent = parent | flatmap(weakref.ref)
    self._name = name
    self._directory = directory
    self._children: t.Dict[str, Project] = {}
    self._extensions: t.Dict[str, t.Any] = {}
    self.tasks = TaskContainer()

  @property
  def project(self) -> 'Project':
    return self

  @property
  def parent(self) -> t.Optional['Project']:
    return self._parent | flatmap(lambda x: x())

  @property
  def name(self) -> str:
    return self._name

  @property
  def path(self) -> str:
    parent = self.parent
    if parent is not None:
      return parent.path + ':' + self._name
    return self._name

  @property
  def directory(self) -> Path:
    return self._directory

  @property
  def build_directory(self) -> Path:
    return self._directory.joinpath(self.DEFAULT_BUILD_DIRECTORY_NAME)

  @classmethod
  def from_directory(cls, parent: t.Optional['Project'], directory: str) -> 'Project':
    path = Path(directory).resolve()
    return Project(parent, path.name, path)

  def run_build_script(self, filename: str) -> None:
    run_file(self, {}, filename)

  def add_child_project(self, project: 'Project') -> None:
    assert project.parent is self
    if project.name in self._children:
      raise ValueError(f'project name {project.path!r} is already in use')
    self._children[project.name] = project

  def iter_sub_projects(self, recursive: bool = True) -> t.Iterator['Project']:
    for child in self._children.values():
      yield child
      if recursive:
        yield from child.iter_sub_projects(True)

  def iter_all_tasks(self) -> t.Iterator[Task]:
    yield from self.tasks.values()
    for child_project in self.iter_sub_projects(True):
      yield from child_project.tasks.values()

  def all_projects(self, configure: t.Callable[['Project'], None]) -> None:
    configure(self)
    self.sub_projects(configure)

  def sub_projects(self, configure: t.Callable[['Project'], None]) -> None:
    for project in self.iter_sub_projects():
      configure(project)

  def task(self, name: str, task_type: t.Type[T_Task] = Task) -> T_Task:
    """
    Registers a new task with the specified *name* and of the *task_type* in the project and
    returns it.
    """

    task = task_type(self, name)
    if name in self.tasks:
      raise ValueError(f'task name {task.path!r} already in use')
    self.tasks[name] = task
    return task

  def apply(self, plugin_name: str) -> None:
    """
    Apply a plugin with the specified name to the project.
    """

    apply_plugin(plugin_name, self)

  def register_extension(self, name: str, obj: t.Any) -> None:
    """
    Register an "extension". Effectively this publishes a name into the Project that can be
    resolved by the Kahmi runtime. This is usually called when plugins are applied to a project
    to register default tasks, task factories and task and action types.
    """

    if name in self._extensions:
      raise ValueError(f'extension {name!r} already registered to project {self.path!r}')
    self._extensions[name] = obj

  # NameProvider

  def lookup_name(self, name: str) -> t.Any:
    return self._extensions[name]
