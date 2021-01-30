
import os
import typing as t
import subprocess
from dataclasses import dataclass, field

from overrides import overrides

from kahmi.build.model import Action, Task


@dataclass
class CommandAction(Action):
  """
  Represents an action to run one or more commands on the shell.
  """

  commands: t.List[t.List[str]] = field(default_factory=list)
  working_dir: t.Optional[str] = None
  environ: t.Optional[t.Dict[str, str]] = field(default_factory=dict)

  @overrides
  def execute(self, task: Task) -> None:
    env = os.environ.copy()
    env.update(self.environ or {})

    for command in self.commands:
      subprocess.call(command, env=env, cwd=self.working_dir)

    task.did_work = True
