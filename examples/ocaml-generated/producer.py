

from kahmi.build.core import LambdaAction
from kahmi.build.model import Project, Property, Task


class ProducerTask(Task):
  output_file: Property[str] = Property(None, Task.Output)
  content: Property[str] = Property(None, Task.Input)

  def configure(self, closure):
    closure(self)
    self.performs(LambdaAction(lambda _: self.write_file()))

  def write_file(self):
    with open(self.output_file.get(), 'w') as fp:
      fp.write(self.content.get())


def apply(project: Project) -> None:
  project.register_extension('ProducerTask', ProducerTask)
