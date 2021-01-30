
"""
Utility to execute a Python function in a subprocess while capturing the output.
"""

import contextlib
import io
import multiprocessing as mp
import os
import select
import sys
import traceback
import types
import typing as t

T = t.TypeVar('T')

# TODO(NiklasRosenstein): Handle signals to kill running processes.


def _internal_worker(
  func: t.Callable[[], t.Any],
  queue: mp.Queue,
  print_traceback: bool = True,
) -> None:
  """
  Internal function that is ultimately the target of a #mp.Process. The *queue* expects the
  pipe file-descriptor and sends back the result and formatted exception tracebackas two separate
  items. If there was an exception, the result will be #None.
  """

  fd = queue.get_nowait()
  os.dup2(fd, sys.stdout.fileno())
  os.dup2(fd, sys.stderr.fileno())
  sys.stdin.close()

  try:
    result = func()
    exc_info = None
  except BaseException:
    result = None
    exc_info = traceback.format_exc()  # Would send the exception info, but traceback cannot be pickled.
    if print_traceback:
      traceback.print_exc()
  else:
    os.close(fd)

  queue.put_nowait(result)
  queue.put_nowait(exc_info)


def run_in_process(
  func: t.Callable[[], T],
  capture: bool = True,
  on_output: t.Optional[t.Callable[[bytes], None]] = None,
  print_traceback: bool = True,
) -> t.Tuple[t.Optional[T], t.Optional[str], t.BinaryIO]:
  """
  Runs the *task* in a separate process and blocks until it is complete. If either *capture*
  is enabled or *on_output* is specified, the output of the process is directed into a pipe,
  otherwise the output is sent to stdout. If both *on_output* and *capture* are provided/enabled,
  *on_output* takes precedence and the returned #t.BinaryIO will be empty.

  Returns:
  - The value returned by *func*, or #None if an exception ocurred in the function.
  - The exception traceback pre-formatted if an exception ocurred.
  - The output of the subprocess as a #io.BytesIO.
  """

  with contextlib.ExitStack() as ctx:
    if capture or on_output:
      pipe_r, pipe_w = os.pipe()
    else:
      pipe_r, pipe_w, pipe_rfp, pipe_wfp = None, None, None, None

    queue = mp.Queue()

    # Send the write end of the pipe to the process.
    queue.put(pipe_w)

    # Create a process to execute the task.
    process = mp.Process(target=_internal_worker, args=(func, queue, print_traceback))
    process.start()

    buffer = io.BytesIO()

    if capture:
      # Read from the pipe and buffer the output.
      os.set_blocking(pipe_r, False)
      while process.is_alive():
        select.select([pipe_r], [], [], 0.5)
        try:
          data = os.read(pipe_r, 4096)
        except BlockingIOError:
          continue
        if on_output:
          on_output(data)
        else:
          buffer.write(data)

    process.join()
    result: t.Optional[T] = queue.get_nowait()
    tb: t.Optional[str] = queue.get_nowait()

  return (result, tb, buffer)
