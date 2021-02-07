
import os
import typing as t
import weakref
from pathlib import Path

from kahmi.dsl import NameProvider, run_file
from kahmi.dsl.macros import get_macro_plugin
from nr.functional import flatmap
from overrides import overrides  # type: ignore

from .configurable import StrictConfigurable
from .task import Task
from .task_container import TaskContainer
from .plugin import apply_plugin
from ..util.preconditions import check_not_none

if t.TYPE_CHECKING:
  from .environment import Environment

T_Task = t.TypeVar('T_Task', bound=Task)


class Project(StrictConfigurable, NameProvider):

  DEFAULT_BUILD_DIRECTORY_NAME = '.build'

  def __init__(self, env: 'Environment', parent: t.Optional['Project'], name: str, directory: Path) -> None:
    assert name, "project name cannot be empty"
    assert isinstance(directory, Path), "directory must be Path instance"
    self._env = weakref.ref(env)
    self._parent = parent | flatmap(weakref.ref)
    self._name = name
    self._directory = directory.resolve()
    self._children: t.Dict[str, Project] = {}
    self._extensions: t.Dict[str, t.Any] = {}
    self.tasks = TaskContainer()

  @property
  def env(self) -> 'Environment':
    return check_not_none(self._env(), 'lost reference to Environment')

  @property
  def project(self) -> 'Project':
    return self

  @property
  def parent(self) -> t.Optional['Project']:
    return self._parent | flatmap(lambda x: x())

  @property
  def root(self) -> 'Project':
    project = self
    while project.parent:
      project = project.parent
    return project

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

  @property
  def extensions(self) -> t.Dict[str, t.Any]:
    return self._extensions

  @classmethod
  def from_directory(cls, env: 'Environment', parent: t.Optional['Project'], directory: str) -> 'Project':
    path = Path(directory).resolve()
    return Project(env, parent, path.name, path)

  def run_build_script(self, filename: str) -> None:
    run_file(self, {}, filename, macros={'yaml': get_macro_plugin('yaml')()})

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

  def task(self, name: str, task_type: t.Optional[t.Type[T_Task]] = None) -> T_Task:
    """
    Registers a new task with the specified *name* and of the *task_type* in the project and
    returns it.
    """

    task = (task_type or Task)(self, name)
    if name in self.tasks:
      raise ValueError(f'task name {task.path!r} already in use')
    self.tasks[name] = task
    return t.cast(T_Task, task)  # NOTE: mypy-workaround

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

  def resolve_tasks(self, selectors: t.List[str]) -> t.Iterator[Task]:
    """
    Given a list of task selectors, returns a list of the matched tasks. If at least one selector
    does not match one task, a #ValueError is raised.
    """

    selected: t.List[Task] = []
    unmatched: t.Set[str] = set(selectors)

    root = self.root

    for task in root.iter_all_tasks():
      matches = False
      for arg in selectors:
        if arg.startswith(':'):
          full_arg = self.name + arg
          if task.path == full_arg:
            matches = True
            break
        if (arg == task.path) or (task.group and arg == (':' + task.group)):
          matches = True
          break

      if matches:
        selected.append(task)
        unmatched.discard(arg)
        break

    if unmatched:
      raise ValueError('unmatched selectors: ' + ', '.join(unmatched))

    return selected

  @overrides
  def _lookup_name(self, name: str) -> t.Any:
    return self._extensions[name]


class ProjectGraphHelper:

  def __init__(self, project: Project) -> None:
    self._project = weakref.ref(project)

  def is_selected(self, task_name: t.Union[str, t.List[str]]) -> bool:
    """
    Returns True if any of the specified tasks are selected in the build graph. Note that
    the selection data is only available
    """


