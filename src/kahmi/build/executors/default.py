
import contextlib
import logging
import io
import os
import platform
import select
import sys
import tempfile
import textwrap
import threading
import time
import typing as t

from overrides import overrides  # type: ignore
from termcolor import colored

from kahmi.build.model import BuildGraph, Task
from pathos.multiprocessing import ProcessingPool  # type: ignore
from .base import Executor, ExecListener

LOG = logging.getLogger(__name__)
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


class FifoMaker:

  def __init__(self, path: str, timeout: int, mode: int = 0o666) -> None:
    self._path = path
    self._timeout = timeout
    self._mode = mode
    self._tstart: t.Optional[int] = None
    self._thread: t.Optional[threading.Thread] = None
    self._exception: t.Optional[BaseException] = None

  def _open_fifo_worker(self, fifo_opened: threading.Event) -> None:
    try:
      fifo_opened.set()
      # NOTE (nrosenstein): Herein lies the period of time in which the FIFO creation can still
      #   go wrong.
      try:
        os.mkfifo(self._path, mode=self._mode)
      except FileExistsError as exc:
        LOG.exception('Was unable to open fifo %r because file exists. This hints at a race '
          'condition where the child process was able to open the path for writing before '
          'mkfifo() was called.', self._path)
        raise
    except BaseException as exc:
      self._exception = exc
    finally:
      fifo_opened.set()

  def __enter__(self) -> 'FifoMaker':
    return self

  def __exit__(self, *a) -> None:
    self.remove()

  def create(self) -> 'FifoMaker':
    """
    Create the FIFO and return. This blocks until the #os.mkfifo() call was made.
    """

    if self._thread is not None:
      raise RuntimeError('cannot create the FIFO twice')

    fifo_opened = threading.Event()
    self._thread = threading.Thread(target=self._open_fifo_worker, args=(fifo_opened,))
    self._thread.start()
    self._tstart = time.perf_counter()
    # Wait for the FIFO to open, then return to the caller.
    fifo_opened.wait(timeout=self._timeout)
    return self

  def open_read(self) -> t.BinaryIO:
    """
    Open the FIFO for reading. This blocks until the FIFO was connected to by another process
    or the timeout since calling #create() is exceeded.
    """

    if self._thread is None:
      raise RuntimeError('call create() before open_read()')
    assert self._tstart is not None

    # Wait for the FIFO to be connected, then return to the caller. If we exceed the timeout,
    # then we assume the FIFO did not connect and abort the process.
    self._thread.join(timeout=self._timeout - (time.perf_counter() - self._tstart))
    if self._thread.is_alive():
      with open(self._path, 'wb'):
        pass
      self.remove()
      self._thread.join()
      raise RuntimeError(f'opening fifo {self._path!r} timed out after {self._timeout} seconds')

    if self._exception is not None:
      raise self._exception

    return open(self._path, 'rb')

  def remove(self) -> None:
    try:
      os.remove(self._path)
    except FileNotFoundError:
      pass


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
  on_output: t.Optional[t.Callable[[bytes], t.Any]] = None,
) -> T:
  """
  Submits a function to the specified *processing_pool* and captures it's stdout via a named pipe
  to pass it into #on_output() as soon as data becomes available. The result of the function is
  returned. If an exception occurs in the function, it will be propagated to the caller.
  """

  with contextlib.ExitStack() as ctx:
    fifo_path = tempfile.mktemp(prefix='kahmi-fifo-')
    fifo = ctx.enter_context(FifoMaker(fifo_path, timeout=5))
    fifo.create()
    result = processing_pool.apipe(_stream_func_async_internal, func, fifo_path)
    output = ctx.enter_context(fifo.open_read())
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
    self._sequential = parallelism == 1

  def _execute(self, task: Task) -> Task:
    task.execute()
    task.reraise_error()
    return task

  def _run_single_task(self, task: Task) -> str:
    self.LOG.info('Running task `%s`', task.path)

    if self._sequential:
      # TODO: Capture stdout
      task.execute()
      return ''

    buffer = io.BytesIO()
    try:
      new_task = stream_func_async(
        self._process_pool,
        lambda: self._execute(task),
        buffer.write)
    except BaseException as exc:
      task.executed = True
      task.exception = exc
    else:
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
      return task.exception is not None

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
