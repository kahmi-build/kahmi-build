
import typing as t

from .task import Task


class TaskContainer(dict, t.MutableMapping[str, Task]):
  """
  A container for task objects.
  """
