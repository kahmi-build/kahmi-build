
import enum
import hashlib
import json
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


class TaskStatus(enum.Enum):
  #: The task status was not yet calculated.
  UNKNOWN = enum.auto()

  #: The task status has not been computed.
  PENDING = enum.auto()

  #: The task is up to date.
  UPTODATE = enum.auto()

  #: External factors contributed to the task to not be executed.
  SKIPPED = enum.auto()

  #: The task executed successfully.
  FINISHED = enum.auto()

  #: The task execution resulted in an error.
  ERROR = enum.auto()


TaskStatus.COMPLETED = (TaskStatus.UPTODATE, TaskStatus.SKIPPED, TaskStatus.FINISHED)


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

    # Data we store only if the task was de/serialized.
    self._is_deserialized: bool = False
    self._cached_path: t.Optional[str] = None

    # We store task dependencies as weakrefs so they don't get serialized by dill.
    self._dependencies: t.List[weakref.ReferenceType[Task]] = []
    self._finalizers: t.List[weakref.ReferenceType[Task]] = []

    self.description: t.Optional[str] = None
    self.group: t.Optional[str] = None
    self.dirty: t.Optional[bool] = None
    self.executed: bool = False
    self.did_work: bool = False
    self.default: bool = True
    self.public: bool = True
    self.exception: t.Optional[BaseException] = None
    self.sync_io: bool = False  #: Stream the output of the task if possible, otherwhise print it after it's completed.

  def __getstate__(self):
    # NOTE(nrosenstein): We explicitly drop the reference to the project because we want to
    #   avoid that it becomes copied into another processed when executing a task with the
    #   DefaultExecutor.
    s = self.__dict__.copy()
    s['_project'] = None
    s['_is_deserialized'] = True
    s['_cached_path'] = self.path
    return s

  def __setstate__(self, state):
    self.__dict__ = state.copy()
    self.__dict__['_project'] = None

  def __repr__(self) -> str:
    return f'<Task {self.path!r} (type: {type(self).__name__})>'

  @property
  def project(self) -> 'Project':
    if self._is_deserialized:
      raise RuntimeError('cannot access Project in deserialized Task')
    return check_not_none(self._project(), 'lost reference to project')

  @property
  def name(self) -> str:
    return self._name

  @property
  def path(self) -> str:
    if self._cached_path:
      return self._cached_path
    return self.project.path + ':' + self._name

  @property
  def group_path(self) -> t.Optional[str]:
    if not self.group:
      return None
    if self._cached_path:
      return self._cached_path.rpartition(':')[0] + ':' + self.group
    return self.project.path + ':' + self.group

  @property
  def actions(self) -> t.List[Action]:
    """ Returns a copy of the task's action list. """

    return self._actions[:]

  @property
  def dependencies(self) -> t.List['Task']:
    """ Returns a copy of the task's direct dependencies list. """

    return [check_not_none(t(), 'lost reference to task') for t in self._dependencies]

  @property
  def finalizers(self) -> t.List['Task']:
    """ Returns a copy of the task's finalizer list. """

    return [check_not_none(t(), 'lost reference to task') for t in self._finalizers]

  @property
  def status(self) -> TaskStatus:
    if self.exception:
      return TaskStatus.ERROR
    elif self.executed:
      if self.did_work:
        return TaskStatus.FINISHED
      return TaskStatus.SKIPPED
    elif self.dirty is None:
      return TaskStatus.UNKNOWN
    elif self.dirty:
      return TaskStatus.PENDING
    else:
      return TaskStatus.UPTODATE

  def before_execute(self) -> None:
    # TODO(nrosenstein): When to use skipped? Should we delegate to actions?
    inputs = self.get_task_inputs()
    if not inputs.files and not inputs.values:
      self.dirty = True
    else:
      self.dirty = self.project.env.state_tracker.task_inputs_changed(self, inputs)

  def execute(self) -> None:
    """
    Executes the task by running all it's actions. Exceptions that arise during the execution
    are caught and stored in the task.
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

  def after_execute(self) -> None:
    self.project.env.state_tracker.task_finished(self, self.get_task_inputs())

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

  def get_task_inputs(self) -> 'TaskInputs':
    inputs = TaskInputs()

    for key, prop in sorted(self.get_props().items(), key=lambda t: t[0]):
      check_instance_of(prop, Property, lambda: f'{type(self).__name__}.{key}')

      if TaskPropertyType.Input in prop.markers:
        adder = inputs.set_input_value
      elif TaskPropertyType.InputFile in prop.markers:
        adder = inputs.set_input_files
      else:
        continue

      value = prop.or_none()
      if isinstance(value, str):
        adder(key, value)
      elif isinstance(value, list):
        # TODO (nrosenstein): Verify that the property actually returned a list of _strings_?
        adder(key, value)
      else:
        raise RuntimeError(f'property {type(self).__name__}.{key} is marked with '
          'TaskPropertyType.Input, thus it is expected to be populated with a value of type '
          f'str or List[str], found {type(value).__name__}')

    return inputs


class TaskInputs:

  def __init__(self) -> None:
    self.files: t.Dict[str, t.List[str]] = {}
    self.values: t.Dict[str, t.Any] = {}

  def set_input_value(self, key: str, value: t.Any) -> None:
    self.values[key] = value

  def set_input_files(self, key: str, value: t.Union[str, t.List[str]]) -> None:
    if isinstance(value, str):
      value = [value]
    elif not isinstance(value, list):
      raise TypeError(f'task input file must be str or List[str], got {type(value).__name__}')
    self.files[key] = value

  def md5sum(self) -> str:
    hasher = hashlib.md5()

    payload = {'files': self.files, 'values': self.values}
    hasher.update(json.dumps(payload, sort_keys=True).encode('utf8'))

    # Take the hash of input files into account.
    for path in sorted(f for files in self.files.values() for f in files):
      try:
        with open(path, 'rb') as fp:
          while True:
            data = fp.read(8096)
            if not data:
              break
            hasher.update(data)
      except (FileNotFoundError, NotADirectoryError):
        pass

    return hasher.hexdigest()
