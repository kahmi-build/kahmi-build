
import types
import typing as t

T = t.TypeVar('T')


class Configurable:
  """
  Base class for objects that are configurable via closures. The default implementation of
  #configure() simply calls the closure with the object.
  """

  def configure(self: T, closure: t.Callable[[T], None]) -> None:
    closure(self)


class StrictConfigurable(Configurable):
  """
  Base class for objects that are configurable via closures and do not accept setting new
  attributes within the closure.
  """

  __in_closure: bool = False

  def __setattr__(self, name: str, value: t.Any) -> None:
    if self.__in_closure:
      if not hasattr(self, name):
        raise AttributeError(f'{type(self).__name__} has no attribute {name!r}')
      if hasattr(type(self), name):
        class_level_val = getattr(type(self), name)
        if isinstance(class_level_val, types.FunctionType):
          raise AttributeError(f'{type(self).__name__}.{name} cannot be overwritten')
    super().__setattr__(name, value)

  def configure(self: T, closure: t.Callable[[T], None]) -> None:
    self.__in_closure = True  # type: ignore
    try:
      Configurable.configure(self, closure)
    finally:
      self.__in_closure = False   # type: ignore
