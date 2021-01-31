
import os
import typing as t
import subprocess
from dataclasses import dataclass, field

from overrides import overrides

from kahmi.build.model import Action, Task


@dataclass
class LambdaAction(Action):
  """
  Represents an action to run one or more commands on the shell.
  """

  func: t.Callable[[Task], None]

  @overrides
  def execute(self, task: Task) -> None:
    self.func(task)
    task.did_work = True
