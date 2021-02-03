
import typing as t
from dataclasses import dataclass

from overrides import overrides  # type: ignore

from kahmi.build.model import Action, Task


@dataclass
class LambdaAction(Action):
  """
  Represents an action to run one or more commands on the shell.
  """

  func: t.Callable[[Task], None]

  @overrides
  def execute(self, task: Task) -> None:
    self.func(task)  # type: ignore
    task.did_work = True
