
"""
Provides a simple interface to building OCaml applications.
"""

import os
import typing as t

from kahmi.build.core import CreateDirAction, CommandAction
from kahmi.build.model import Project, Property, ListProperty, Task, task_factory


class OcamlApplication(Task):

  srcs: ListProperty[str] = ListProperty([], Task.InputFile)
  standalone: Property[bool] = Property(True)

  # Properties that construct the output filename.
  output_directory: Property[str] = Property(lambda self: os.path.join(self.project.build_directory, 'ocaml', self.name))
  product_name: Property[str] = Property('main')
  suffix: Property[str] = Property()

  output_file: Property[str] = Property(None, Task.Output)

  @suffix.default
  def suffix(self) -> str:
    if self.standalone.get() and os.name == 'nt':
      return '.exe'
    elif not self.standalone:
      return '.cma'
    return ''

  @output_file.default
  def output_file(self) -> str:
    return os.path.join(self.output_directory.get(), self.product_name.get() + self.suffix.get())

  def setup(self):
    self.output_file.default(self.product_name.map(
      lambda v: f'{self.output_directory.get()}/{self.product_name.get()}.{self.suffix.get()}'))

  def configure(self, closure):
    closure(self)

    self.output_file.finalize()
    command = ['ocamlopt' if self.standalone.get() else 'ocamlc']
    command += ['-o'] + [self.output_file.get()] + self.srcs.get()

    self.performs(CreateDirAction(os.path.dirname(self.output_file.get())))
    self.performs(CommandAction([command]))

    # TODO(nrosenstein): Add cleanup action to remove .cmi/cmx/.o files?
    #   There doesn't seem to be an option in the Ocaml compiler to change their
    #   output location.

    run_task = self.project.task(self.name + 'Run')
    run_task.group = 'run'
    run_task.default = False
    run_task.depends_on(self)
    run_task.performs(CommandAction([[self.output_file.get()]]))


def apply(project: Project) -> None:
  project.register_extension('OcamlApplication', OcamlApplication)
  project.register_extension('ocamlApplication', task_factory(project, OcamlApplication, 'ocamlApplication'))
