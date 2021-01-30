
import typing as t

T = t.TypeVar('T')


class Configurable:

  def configure(self: T, closure: t.Callable[[T], None]) -> None:
    closure(self)
