
import abc
import os

from nr.caching.api import KeyDoesNotExist, KeyValueStore
from nr.caching.sqlite import SqliteStore
from overrides import overrides

from .task import Task, TaskInputs


class StateTracker(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def task_inputs_changed(self, task: Task, inputs: TaskInputs) -> bool:
    pass

  @abc.abstractmethod
  def task_finished(self, task: Task, inputs: TaskInputs) -> None:
    pass



class NoStateTracker(StateTracker):

  def task_inputs_changed(self, task: Task, inputs: TaskInputs) -> bool:
    return True

  def task_finished(self, task: Task, inputs: TaskInputs) -> None:
    return None


class SqliteStateTracker(StateTracker):
  """
  Note: Cannot be shared between processes -- actually multiprocessing seems to run into a
  deadlock when trying to serialize/deserialize it.
  """

  def __init__(self, filename: str) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    self._store: KeyValueStore = SqliteStore(filename).namespace('tasks')

  def task_inputs_changed(self, task: Task, inputs: TaskInputs) -> bool:
    try:
      stored_checksum = self._store.load(task.path).decode('ascii')
    except KeyDoesNotExist:
      return True
    return stored_checksum != inputs.md5sum()

  def task_finished(self, task: Task, inputs: TaskInputs) -> None:
    if task.exception:
      self._store.store(task.path, b'', 0)
    else:
      self._store.store(task.path, inputs.md5sum().encode('ascii'))
