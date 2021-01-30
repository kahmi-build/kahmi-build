
import glob
import os
import typing as t

from .task import Task


class FileCollection:
  """
  Represents a collection of files and the tasks that the files are dependant on.
  """

  def __init__(self) -> None:
    self._files: t.List[str] = []
    self._tasks: t.List[Task] = []

  def __repr__(self) -> str:
    return f'FileCollection(files={self._files!r}, tasks={self._tasks!r})'

  @property
  def files(self) -> t.List[str]:
    return self._files[:]

  @property
  def tasks(self) -> t.List[Task]:
    return self._tasks[:]

  def normalize(self, directory: str) -> None:
    """
    Ensure every relative path in the collection is absolute using *directory* and expand
    glob patterns in the paths.
    """

    if not os.path.isabs(directory):
      raise ValueError(f'directory must be absolute: {directory!r}')

    def _optglob(path: str) -> t.List[str]:
      if '*' in path:  # TODO(NiklasRosenstein): Check for other characters that indicate a glob pattern
        return glob.glob(path)
      return [path]

    self._files[:] = (x for f in self._files for x in _optglob(os.path.join(directory, f)))

  @classmethod
  def from_any_list(cls, lst: t.Sequence[t.Any]) -> 'FileCollection':
    """
    Produces a #FileCollection from a list of items that can be of a variety of types:

    * A plain string, in which case it is interpreted as a single filename.
    * A Task, in which case the task's output files are expanded into the collection's files and
      the task is added to the collection's tasks.
    * A FileCollection
    * A list of any of the above.
    """

    result = cls()

    for item in lst:
      if isinstance(item, str):
        result._files.append(item)
        continue
      elif isinstance(item, Task):
        # TODO: Take the task's outputs.
        result._tasks.append(item)
        continue
      elif isinstance(item, t.Sequence):
        item = cls.from_any_list(item)
      if isinstance(item, FileCollection):
        result._files.extend(item._files)
        result._tasks.extend(item._tasks)
        continue
      raise TypeError(f'encountered unexpected {type(item).__name__}')

    return result
