
import contextlib
import logging
import io
import os
import select
import sys
import tempfile
import textwrap
import threading
import typing as t

from overrides import overrides
from termcolor import colored

from kahmi.build.model import BuildGraph, Task
from pathos.multiprocessing import ProcessingPool
from .base import Executor, ExecListener

T = t.TypeVar('T')

if not hasattr(os, 'mkfifo'):
  raise EnvironmentError('default executor requires os.mkfifo() support')

#STATUS_COLORS = {
#  Status.SKIPPED: 'grey',
#  Status.SUCCESS: 'green',
#  Status.UNEXPECTED: 'yellow',
#  Status.ERROR: 'red',
#  Status.DEPENDENCY_ERROR: 'red',
#}


def _safe_mkfifo(path: str, timeout: int, mode: int = 0o666) -> t.BinaryIO:
  """
  Creates a fifo and waits at max *timeout* seconds before cancelling the operation and raising
  a #RuntimeError instead. Returns the readable end of the fifo on success.
  """

  exception: t.Optional[BaseException] = None

  def _worker():
    nonlocal exception
    try:
      os.mkfifo(path)
    except BaseException as exc:
      exception = exc

  thread = threading.Thread(target=_worker)
  thread.start()
  thread.join(timeout=timeout)

  if thread.is_alive():
    with open(path, 'wb'):
      pass
    os.remove(path)
    thread.join()
    raise RuntimeError(f'opening fifo {path!r} timed out after {timeout} seconds')

  if exception is not None:
    raise exception

  return open(path, 'rb')


def _stream_func_async_internal(func: t.Callable[[], T], fifo_path: str) -> T:
  """ Internal helper for #stream_func_async(). """

  with open(fifo_path, 'wb') as fp:
    os.dup2(fp.fileno(), sys.stdout.fileno())
    os.dup2(fp.fileno(), sys.stderr.fileno())
    sys.stdin.close()
    return func()


def stream_func_async(
  processing_pool: ProcessingPool,
  func: t.Callable[[], T],
  on_output: t.Optional[t.Callable[[bytes], None]] = None,
) -> T:
  """
  Submits a function to the specified *processing_pool* and captures it's stdout via a named pipe
  to pass it into #on_output() as soon as data becomes available. The result of the function is
  returned. If an exception occurs in the function, it will be propagated to the caller.
  """

  with contextlib.ExitStack() as ctx:
    fifo_path = tempfile.mktemp(prefix='kahmi-fifo-')
    ctx.push(lambda *a: (os.remove(fifo_path) if os.path.exists(fifo_path) else None, None)[1])
    result = processing_pool.apipe(_stream_func_async_internal, func, fifo_path)
    output = ctx.enter_context(_safe_mkfifo(fifo_path, timeout=5))
    os.set_blocking(output.fileno(), False)
    while not result.ready():
      # We use select() to limit busy polling activity for long-running tasks.
      select.select([output], [], [], 0.01)
      try:
        data = output.read(4096)
      except BlockingIOError:
        continue
      if data is None:
        break
      if on_output is not None:
        on_output(data)

    return result.get()


class DefaultProgressPrinter(ExecListener):

  def __init__(self, always_show_output: bool = False) -> None:
    self.always_show_output = always_show_output

  def task_execute_begin(self, task: Task) -> None:
    print(colored(task.path, 'cyan'), end=' ...', flush=True)

  def task_execute_end(self, task: Task, output: str) -> None:
    print()
    if self.always_show_output or task.sync_io or task.group == 'run' or task.exception:
      output = textwrap.indent(output, '|  ')
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

  LOG = logging.getLogger(__name__ + '.' + __qualname__)  # type: ignore

  def __init__(self,
    listener: t.Optional[ExecListener] = None,
    parallelism: t.Optional[int] = None,
  ) -> None:

    self._listener = listener or DefaultProgressPrinter(False)
    self._process_pool = ProcessingPool(parallelism)

  def _run_single_task(self, task: Task) -> str:
    self.LOG.info('Running task `%s`', task.path)

    buffer = io.BytesIO()
    new_task = stream_func_async(
      self._process_pool,
      lambda: (task.execute(), task)[1],
      buffer.write)

    # Inherit properties from the task's new status.
    for key, value in vars(new_task).items():
      if key.startswith('_'):
        continue
      if value != getattr(task, key):
        setattr(task, key, value)

    assert task.executed, task
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
    with self._process_pool:
      for task in graph.topological_order():
        self.run(task)
        task.reraise_error()
