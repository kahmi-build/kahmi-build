
"""
Provides a simple interface to building OCaml applications.
"""

import os
import typing as t

from kahmi.build.core import CreateDirAction, CommandAction
from kahmi.build.model import FileCollection, Project, Task, task_factory


class OcamlApplication(Task):

  srcs: t.Sequence[t.Any] = ()
  standalone: bool = False
  product_name: t.Optional[str] = None
  output_directory: t.Optional[str] = None

  def configure(self, closure):
    closure(self)

    collection = FileCollection.from_any_list(self.srcs)
    collection.normalize(self.project.directory)
    self.depends_on(*collection.tasks)

    output_directory = self.output_directory or os.path.join(self.project.build_directory, 'ocaml')
    product = os.path.join(output_directory, self.product_name or self.project.name)
    if self.standalone and os.name == 'nt':
      product += '.exe'
    elif not self.standalone:
      product += '.cma'

    command = ['ocamlopt' if self.standalone else 'ocamlc']
    command += ['-o'] + [product] + collection.files

    self.performs(CreateDirAction(output_directory))
    self.performs(CommandAction([command]))

    # TODO(nrosenstein): Add cleanup action to remove .cmi/cmx/.o files?
    #   There doesn't seem to be an option in the Ocaml compiler to change their
    #   output location.

    run_task = self.project.task(self.name + 'Run')
    run_task.group = 'run'
    run_task.default = False
    run_task.depends_on(self)
    run_task.performs(CommandAction([[product]]))


def apply(project: Project) -> None:
  project.register_extension('OcamlApplication', OcamlApplication)
  project.register_extension('ocamlApplication', task_factory(project, OcamlApplication, 'ocamlApplication'))
