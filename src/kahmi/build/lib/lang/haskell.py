
"""
Provides a simple interface to building Haskell applications.
"""

import os
import typing as t

from kahmi.build.core import CreateDirAction, CommandAction
from kahmi.build.model import ListProperty, Property, Project, Task, task_factory


class HaskellApplication(Task):

  srcs: ListProperty[str] = ListProperty([], Task.InputFile)
  compiler_flags: ListProperty[str] = ListProperty([])

  # Properties that construct the output filename.
  output_directory: Property[str] = Property(lambda self: os.path.join(self.project.build_directory, 'haskell', self.name))
  product_name: Property[str] = Property('main')
  suffix: Property[str] = Property(lambda self: '.exe' if os.name == 'nt' else '')

  output_file: Property[str] = Property(None, Task.Output)

  @output_file.default
  def output_file(self) -> str:
    return os.path.join(self.output_directory.get(), self.product_name.get() + self.suffix.get())

  def configure(self, closure):
    closure(self)

    output_file = self.output_file.finalize()
    srcs = self.project.files(self.srcs.finalize())
    command = ['ghc', '-o', output_file] + srcs + self.compiler_flags.finalize()
    self.performs(CreateDirAction(os.path.dirname(output_file)))
    self.performs(CommandAction([command]))

    # TODO(nrosenstein): Add cleanup action to remove .hi/.o files?
    #   There doesn't seem to be an option in the Ocaml compiler to change their
    #   output location.

    run_task = self.project.task(self.name + 'Run')
    run_task.group = 'run'
    run_task.default = False
    run_task.depends_on(self)
    run_task.performs(CommandAction([[output_file]]))

  def execute(self):
    super().execute()


def apply(project: Project) -> None:
  project.register_extension('HaskellApplication', HaskellApplication)
  project.register_extension('haskellApplication', task_factory(project, HaskellApplication, 'haskellApplication'))
