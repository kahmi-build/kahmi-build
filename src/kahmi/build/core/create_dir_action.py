
import os
from dataclasses import dataclass

from overrides import overrides  # type: ignore

from kahmi.build.model import Action, Task


@dataclass
class CreateDirAction(Action):
  """
  Represents an action to run one or more commands on the shell.
  """

  directory: str

  @overrides
  def execute(self, task: Task) -> None:
    os.makedirs(self.directory, exist_ok=True)
