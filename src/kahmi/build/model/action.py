
import abc
import typing as t

from .configurable import Configurable

if t.TYPE_CHECKING:
  from .task import Task


class Action(Configurable, metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def execute(self, task: 'Task') -> None:
    """
    Execute the action against the given task object.
    """
