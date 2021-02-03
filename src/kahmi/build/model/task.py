
import enum
import typing as t
import weakref

from .action import Action
from .configurable import StrictConfigurable
from .property import HavingProperties, Property, collect_properties
from ..util.preconditions import check_instance_of, check_not_none

if t.TYPE_CHECKING:
  from .project import Project

T_Action = t.TypeVar('T_Action', bound=Action)


class TaskPropertyType(enum.Enum):
  #: Mark a property as an input to the task. If the property value changes between builds, the
  #: task will be considered out of date.
  Input = enum.auto()

  #: Mark a property as an input file to the task. If the property value or the contents of the
  #: file change, the task will be considered out of date. Only strings or lists of strings can
  #: be input files.
  InputFile = enum.auto()

  #: Mark the property as an input directory to the task. If the property value or the contents
  #: of the directory change, the task will be considered out of date. Only strings or lists of
  #: strings can be input directories.
  InputDir = enum.auto()

  #: Mark a property as the output of a task. Only properties of other tasks that are marked as
  #: outputs will introduce an automatic dependency.
  Output = enum.auto()


class Task(StrictConfigurable, HavingProperties):
  """
  A task represents a single atomic piece of work for a build that is composed of actions and
  configurable through properties. Properties that are set to consume properties of other tasks
  automatically introduce a dependency.

  A subset of the properties can be marked with #Input, #InputFile, #InputDir and #Output to
  indicate how the property is taken into account in the task.
  """

  Input = TaskPropertyType.Input
  InputFile = TaskPropertyType.InputFile
  InputDir = TaskPropertyType.InputDir
  Output = TaskPropertyType.Output

  def __init__(self, project: 'Project', name: str) -> None:
    super().__init__()

    self._project = weakref.ref(project)
    self._name = name
    self._actions: t.List[Action] = []

    # We store task dependencies as weakrefs so they don't get serialized by dill.
    self._dependencies: t.List[weakref.ReferenceType[Task]] = []
    self._finalizers: t.List[weakref.ReferenceType[Task]] = []

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
    return check_not_none(self._project(), 'lost reference to project')

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
    """ Returns a copy of the task's direct dependencies list. """

    return [check_not_none(t(), 'lost reference to task') for t in self._dependencies]

  def compute_all_dependencies(self) -> t.Set['Task']:
    """
    Computes all dependencies of the task, including those inherited through properties.
    """

    result = set(self.dependencies)

    for key, prop in self.get_props().items():
      check_instance_of(prop, Property, lambda: f'{type(self).__name__}.{key}')
      for consumed_prop in prop.dependencies():
        if TaskPropertyType.Output in consumed_prop.markers and \
            isinstance(consumed_prop.origin, Task):
          result.add(consumed_prop.origin)

    return result

  @property
  def finalizers(self) -> t.List['Task']:
    """ Returns a copy of the task's finalizer list. """

    return [check_not_none(t(), 'lost reference to task') for t in self._finalizers]

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
      check_instance_of(task, Task)
      self._dependencies.append(weakref.ref(task))

  def finalized_by(self, *tasks: 'Task') -> None:
    for task in tasks:
      check_instance_of(task, Task)
      self._finalizers.append(weakref.ref(task))
