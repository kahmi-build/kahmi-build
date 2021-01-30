
"""
Provides a simple interface to building Haskell applications.
"""

import os
import typing as t

from kahmi.build.core import CreateDirAction, CommandAction
from kahmi.build.model import FileCollection, Project, Task, task_factory


class HaskellApplication(Task):

  srcs: t.Sequence[t.Any] = ()
  product_name: t.Optional[str] = None
  compiler_flags: t.Sequence[str] = ()
  output_directory: t.Optional[str] = None

  def configure(self, closure):
    closure(self)

    collection = FileCollection.from_any_list(self.srcs)
    collection.normalize(self.project.directory)
    self.depends_on(*collection.tasks)

    output_directory = self.output_directory or os.path.join(self.project.build_directory, 'haskell')
    product = os.path.join(output_directory, self.product_name or self.project.name)
    if os.name == 'nt':
      product += '.exe'

    command = ['ghc', '-o', product] + collection.files + list(self.compiler_flags)

    self.performs(CreateDirAction(output_directory))
    self.performs(CommandAction([command]))

    # TODO(nrosenstein): Add cleanup action to remove .hi/.o files?
    #   There doesn't seem to be an option in the Ocaml compiler to change their
    #   output location.

    run_task = self.project.task(self.name + 'Run')
    run_task.group = 'run'
    run_task.default = False
    run_task.depends_on(self)
    run_task.performs(CommandAction([[product]]))


def apply(project: Project) -> None:
  project.register_extension('HaskellApplication', HaskellApplication)
  project.register_extension('haskellApplication', task_factory(project, HaskellApplication, 'haskellApplication'))
