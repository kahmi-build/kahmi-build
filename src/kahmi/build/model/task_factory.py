
import typing as t

from .project import Project
from .task import Task

T_Task = t.TypeVar('T_Task', bound=Task)


class task_factory(t.Generic[T_Task]):
  """
  A helper class that is usually registered as an extension in a #Project to provide a default
  task and a factory function with a named task.

  ```python
  myTaskFactory {
    # configure task with default name
  }
  myTaskFactory("myTaskName") {
    # configure task with name "myTaskName"
  }
  ```
  """

  def __init__(self, project: Project, task_type: t.Type[T_Task], default_name: str) -> None:
    self._project = project
    self._task_type = task_type
    self._default_name = default_name

  def __call__(self, name: str) -> T_Task:
    return self._project.task(name, self._task_type)

  def configure(self, closure: t.Callable[[T_Task], None]) -> None:
    self._project.task(self._default_name, self._task_type).configure(closure)
