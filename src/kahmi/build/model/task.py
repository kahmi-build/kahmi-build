
import abc
import typing as t
import weakref

from kahmi.dsl import Configurable

from .action import Action

if t.TYPE_CHECKING:
  from .project import Project

T_Action = t.TypeVar('T_Action', bound=Action)


class Task(Configurable):
  """
  A task represents a single atomic piece of work for a build. Tasks are composed of actions.
  """

  def __init__(self, project: 'Project', name: str):
    self._project = weakref.ref(project)
    self._name = name
    self._actions: t.List[Action] = []
    self._dependencies: t.List[Task] = []
    self._finalizers: t.List[Task] = []
    self.description: t.Optional[str] = None
    self.group: t.Optional[str] = None
    self.executed: bool = False
    self.did_work: bool = False
    self.default: bool = True
    self.public: bool = True
    self.exception: t.Optional[BaseException] = None
    self.sync_io: bool = False  #: Stream the output of the task if possible, otherwhise print it after it's completed.

  def __repr__(self) -> str:
    return f'<Task {self.path!r} (type: {type(self).__name__})>'

  @property
  def project(self) -> 'Project':
    return self._project()

  @property
  def name(self) -> str:
    return self._name

  @property
  def path(self) -> str:
    return self.project.path + ':' + self._name

  @property
  def actions(self) -> t.List[Action]:
    """ Returns a copy of the task's action list. """

    return self._actions[:]

  @property
  def dependencies(self) -> t.List['Task']:
    """ Returns a copy of the task's dependencies list. """

    return self._dependencies[:]

  @property
  def finalizers(self) -> t.List['Task']:
    """ Returns a copy of the task's finalizer list. """

    return self._finalizers[:]

  def execute(self) -> None:
    """
    Executes the task by running all it's actions. Exceptions that arise during the execution
    are caught and stored in the task/
    """

    if self.executed:
      raise RuntimeError(f'task {self.path!r} already executed')

    try:
      for action in self._actions:
        action.execute(self)
    except BaseException as exc:
      self.exception = exc
    finally:
      self.executed = True

  def reraise_error(self) -> None:
    """
    Reraise the error that occurred in the task, if there was one.
    """

    if self.exception is not None:
      raise self.exception

  def performs(self, action: t.Union[T_Action, t.Type[T_Action]]) -> T_Action:
    if isinstance(action, type):
      action = action()
    assert isinstance(action, Action), "action must be an Action instance"
    self._actions.append(action)
    return action

  def depends_on(self, *tasks: 'Task') -> None:
    for task in tasks:
      assert isinstance(task, Task), "task must be a Task instance"
      self._dependencies.append(task)

  def finalized_by(self, *tasks: 'Task') -> None:
    for task in tasks:
      assert isinstance(task, Task), "task must be a Task instance"
      self._finalizers.append(task)
