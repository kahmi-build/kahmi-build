
import textwrap
import typing as t
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from overrides import overrides
from termcolor import colored

from kahmi.build.model import BuildGraph, Task
from .utils.mp import run_in_process
from .base import Executor, ExecListener

#STATUS_COLORS = {
#  Status.SKIPPED: 'grey',
#  Status.SUCCESS: 'green',
#  Status.UNEXPECTED: 'yellow',
#  Status.ERROR: 'red',
#  Status.DEPENDENCY_ERROR: 'red',
#}


class DefaultProgressPrinter(ExecListener):

  def __init__(self, always_show_output: bool = False) -> None:
    self.always_show_output = always_show_output

  def task_execute_begin(self, task: Task) -> None:
    print(colored(task.path, 'cyan'), end=' ...')

  def task_execute_end(self, task: Task, output: str) -> None:
    print()
    if task.sync_io or task.group == 'run':
      print(output.rstrip())
    """
    print('\r' + colored(task.id, 'cyan'), colored(status.name, STATUS_COLORS[status]))
    if not status.is_ok() or status == Status.UNEXPECTED or self.always_show_output:
      output = textwrap.indent(output, '|  ')
      if not status.is_ok():
        output = colored(output, 'red')
      print()
      print(output.rstrip())
      print()
    """


class DefaultExecutor(Executor):
  """
  The default executor for tasks. It expects that tasks are serializable and can be run in
  a separate process using the #multiprocessing module. The output produced by tasks is captured
  and either printed once the task is completed (if *always_show_output* is #True), or otherwise
  only printed when a task failed.
  """

  def __init__(self, listener: t.Optional[ExecListener] = None) -> None:
    self._listener = listener or DefaultProgressPrinter(False)

  def _run_single_task(self, task: Task) -> str:
    _return_value, exc_info, buffer = run_in_process(task.execute)
    # TODO(nrosenstein): We need to read-back the Task properties that have been set during
    #     execution in a separate process.
    task.executed = True
    if exc_info:
      task.exception = RuntimeError(exc_info)  # TODO: better exception type?
    return buffer.getvalue().decode()

  def run(self, task: Task) -> bool:
    """
    Runs the inputs of *task* and then the task itself.
    """

    # TODO: Parallelization

    if task.executed:
      return task.exc_info is not None

    for dep in task.dependencies:
      assert dep.executed, f'dependency {dep.path!r} of task {task.path!r} not executed'

    self._listener.task_execute_begin(task)
    output = self._run_single_task(task)
    self._listener.task_execute_end(task, output)

    # TODO: Call task cleanups

    return True

  @overrides
  def execute_graph(self, graph: BuildGraph) -> None:
    for task in graph.topological_order():
      self.run(task)
      task.reraise_error()
