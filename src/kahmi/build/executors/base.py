
import abc
import typing as t

from kahmi.build.model import BuildGraph, Task


class ExecListener(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def task_execute_begin(self, task: Task) -> None:
    pass

  @abc.abstractmethod
  def task_execute_end(self, task: Task, output: str) -> None:
    pass

  def task_cleanup_begin(self, task: Task) -> None:
    pass  # empty default

  def task_cleanup_end(self, task: Task) -> None:
    pass  # empty default


class Executor(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def execute_graph(self, graph: BuildGraph) -> None:
    pass
