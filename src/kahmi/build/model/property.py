
import abc
import typing as t
import weakref

from kahmi.dsl import PropertyOwner
from overrides import overrides

from ..util.preconditions import check_instance_of, check_not_none

T = t.TypeVar('T')
R = t.TypeVar('R')


class NoValuePresent(Exception):

  def __init__(self, provider: 'Provider[T]') -> None:
    self.provider = provider


class Provider(t.Generic[T], metaclass=abc.ABCMeta):
  """
  A provider just provides a value in potentially lazy way.
  """

  @abc.abstractmethod
  def __bool__(self) -> bool:
    pass

  @abc.abstractmethod
  def get(self) -> T:
    pass

  @abc.abstractmethod
  def visit(self, visitor: t.Callable[['Provider'], bool]) -> None:
    pass

  def or_else(self, value: T) -> T:
    try:
      return self.get()
    except NoValuePresent:
      return value

  def or_none(self) -> t.Optional[T]:
    try:
      return self.get()
    except NoValuePresent:
      return None

  def map(self, func: t.Callable[[T], R]) -> 'Provider[R]':
    return MappedProvider(func, self)

  def flatmap(self, func: t.Callable[[T], 'Provider[R]']) -> 'Provider[R]':
    return FlatMappedProvider(func, self)

  def coalesce(self, provider: 'Provider[T]') -> 'Provider[T]':
    return CoalescingProvider(self, provider)


class MappedProvider(Provider[R]):

  def __init__(self, func: t.Callable[[T], R], sub: Provider[T]) -> None:
    self._func = func
    self._sub = sub

  def __repr__(self) -> str:
    return f'MappedProvider({self._func!r}, {self._sub!r})'

  @overrides
  def __bool__(self) -> bool:
    return bool(self._sub)

  @overrides
  def get(self) -> R:
    return self._func(self._sub.get())

  @overrides
  def visit(self, visitor: t.Callable[[Provider], bool]) -> None:
    if visitor(self):
      self._sub.visit(visitor)
      # Check if the closure captures any properies.
      for cell in (self._func.__closure__ or []):
        if isinstance(cell.cell_contents, Property):
          cell.cell_contents.visit(visitor)


class FlatMappedProvider(Provider[R]):

  def __init__(self, func: t.Callable[[T], Provider[R]], sub: Provider[T]) -> None:
    self._func = func
    self._sub = sub

  def __repr__(self) -> str:
    return f'FlatMappedProvider({self._func!r}, {self._sub!r})'

  @overrides
  def __bool__(self) -> bool:
    value = self._sub.or_none()
    if value is None:
      return False
    return bool(self._func(value))

  @overrides
  def get(self) -> R:
    return self._func(self._sub.get()).get()

  @overrides
  def visit(self, visitor: t.Callable[[Provider], bool]) -> None:
    if visitor(self):
      self._sub.visit(visitor)
      # Check if the closure captures any properies.
      for cell in (self._func.__closure__ or []):
        if isinstance(cell.cell_contents, Property):
          cell.cell_contents.visit(visitor)


class CoalescingProvider(Provider[T]):

  def __init__(self, a: Provider[T], b: Provider[T]) -> None:
    check_not_none(a, 'b cannot be None')
    check_not_none(b, 'b cannot be None')
    self._a = a
    self._b = b

  def __repr__(self) -> str:
    return f'CoalescingProvider({self._a!r}, {self._b!r})'

  @overrides
  def __bool__(self) -> bool:
    return bool(self._a) or bool(self._b)

  @overrides
  def get(self) -> T:
    value = self._a.or_none()
    if value is None:
      value = self._b.or_none()
      if value is None:
        raise NoValuePresent(self)
    return value

  @overrides
  def visit(self, visitor: t.Callable[[Provider], bool]) -> None:
    if visitor(self):
      self._a.visit(visitor)
      self._b.visit(visitor)


class Box(Provider[T]):

  def __init__(self, value: t.Optional[T]) -> None:
    self._value = value

  def __repr__(self) -> str:
    return f'Box({self._value!r})'

  @overrides
  def __bool__(self) -> bool:
    return self._value is not None

  @overrides
  def get(self) -> T:
    if self._value is None:
      raise NoValuePresent(self)
    return self._value

  @overrides
  def visit(self, visitor: t.Callable[[Provider], bool]) -> None:
    if visitor(self) and isinstance(self._value, t.Sequence):
      # Support properties nested in lists.
      for item in self._value:
        if isinstance(item, Provider):
          item.visit(visitor)


class Property(Provider[T]):

  def __init__(self,
    default_value: t.Union[Provider[T], T, None] = None,
    *markers: t.Any,
    name: t.Optional[str] = None,
    origin: t.Optional[t.Callable[[], 'HavingProperties']] = None,
  ) -> None:
    self._markers = list(markers)
    self._name = name
    self._origin = origin
    self._finalized = False
    self._finalize_on_read = False
    self._final_value: t.Optional[T] = None
    self._value: t.Property[T] = Box(None)
    self._default: t.Property[T]
    self._default_func: t.Optional[t.Callable[['HavingProperties'], T]] = None
    self.default(default_value)

  def __repr__(self) -> str:
    status = 'finalized ' if self._finalized else ''
    name = repr(self._name) if self._name else '(anonymous)'
    return f'<{status}Property {name}: {self._value} {self._markers}, {self.origin}>'

  @property
  def markers(self) -> t.Sequence[t.Any]:
    return self._markers

  @property
  def name(self) -> t.Optional[str]:
    return self._name

  @property
  def origin(self) -> t.Optional['HavingProperties']:
    if self._origin is None:
      return None
    origin = self._origin()
    if origin is None:
      raise RuntimeError('lost reference to origin')
    return origin

  @overrides
  def __bool__(self) -> bool:
    return bool(self._value or self._default or self._default_func)

  @overrides
  def get(self) -> T:
    if self._finalized:
      if self._finalize_on_read:
        try:
          self._final_value = self._get_value()
        except NoValuePresent:
          self._final_value = None
        self._finalize_on_read = False
      if self._final_value is None:
        raise NoValuePresent(self)
      return self._final_value
    return self._get_value()

  def _get_value(self) -> T:
    result = self._value.or_none()
    if result is None:
      if self._default_func:
        result = self._default_func(self.origin)
      elif self._default:
        result = self._default.or_none()
    if result is None:
      raise NoValuePresent(self)
    return result

  @overrides
  def visit(self, visitor: t.Callable[['Provider'], bool]) -> None:
    if visitor(self):
      if self._value:
        self._value.visit(visitor)
      else:
        self._default.visit(visitor)

  def set(self, value: t.Union[Provider[T], t.Optional[T]]) -> 'Property[T]':
    if self._finalized:
      raise RuntimeError('Property is finalized')
    if not isinstance(value, Provider):
      value = Box[T](value)
    self._set_value(value)
    return self

  def _set_value(self, value: Provider[T]) -> None:
    check_instance_of(value, Provider)
    self._value = value

  def default(self, value: t.Union[Provider[T], t.Optional[T], t.Callable[['HavingProperties'], T]]) -> 'Property[T]':
    if not isinstance(value, Provider):
      if callable(value):
        self._default_func = value
        self._default = None
      else:
        self._default_func = None
        self._default = Box(value)
    else:
      self._default_func = None
      self._default = value
    return self

  def finalize(self) -> T:
    if not self._finalized or self._finalize_on_read:
      self._final_value = self._get_value()
      self._finalize_on_read = False
      self._finalized = True
    return self._final_value

  def finalize_on_read(self) -> None:
    if not self._finalized:
      self._finalized = True
      self._finalize_on_read = True

  def dependencies(self) -> t.List['Property']:
    return collect_properties(self._value)

  def instantiate(self, origin: 'HavingProperties', name: str) -> 'Property[T]':
    return type(self)(self._default_func or self,
      *self.markers, name=name, origin=weakref.ref(origin))


class ListProperty(Property[t.List[T]]):
  """
  A special property that describes a mutable list of properties.
  """

  # NOTE (nrosenstein): The generic actually points at this being of type Property[t.List[T]],
  #   though we abuse the parent class' by actualling storing _InternvalValueType instead.

  _SingleItem = t.Union[T, Provider[T]]
  _ProviderType = Provider[t.Sequence[T]]
  _RawType = t.Sequence[_SingleItem]
  _InternalValueType = t.Union[_ProviderType, _RawType]

  def __init__(self,
    value: t.Union[_InternalValueType, None] = None,
    *markers: t.Any,
    name: t.Optional[str] = None,
    origin: t.Optional[t.Callable[[], 'HavingProperties']] = None,
  ) -> None:
    super().__init__(value or [], *markers, name=name, origin=origin)

  @overrides
  def visit(self, visitor: t.Callable[['Provider'], bool]) -> None:
    if visitor(self):
      for item in self._values:
        item.visit(visitor)

  @overrides
  def _get_value(self) -> t.List[T]:
    result: t.List[T] = []
    for item in super()._get_value():
      if isinstance(item, Provider):
        try:
          result.append(item.get())
        except NoValuePresent:
          pass
      else:
        result.append(item)
    return result

  def add(self, value: _SingleItem) -> None:
    def _flat(left: ListProperty._InternalValueType) -> ListProperty._InternalValueType:
      if left is None:
        left = []
      else:
        left = list(left)
      left.append(value)
      return left
    if not self._value:
      self._value = Box([])
    self._value = self._value.map(_flat)

  def extend(self, value: _InternalValueType) -> None:
    def _flat(left: ListProperty._InternalValueType) -> ListProperty._InternalValueType:
      if left is None:
        left = []
      else:
        left = list(left)
      left.extend(value)
      return left
    if not self._value:
      self._value = Box([])
    self._value = self._value.map(_flat)


class HavingProperties(PropertyOwner):
  """
  Mixin for classes that make use of properties by defining them on the class-level. The
  constructor will automatically parse the available properties from the type annotations
  and initialize the fields with #Property instances. If a #Property is defined on the
  class-level, that property is used as the default value.
  """

  def __init__(self):
    for key, default in self.get_props_defaults().items():
      setattr(self, key, default.instantiate(self, key))

  @classmethod
  def get_props_defaults(cls) -> t.Dict[str, Property]:
    # We store a cache of the computed properties per the class annotations on the class object
    # itself. If that's already computed, we safe ourselves some work.
    cache_key = '__HavingProperties_props_defaults'
    if cache_key in vars(cls):
      return getattr(cls, cache_key)

    _notset = object()

    props: t.Dict[str, Property] = {}
    for key, value in t.get_type_hints(cls).items():

      is_property_instance = isinstance(value, type) and issubclass(value, Property)
      is_property_alias = type(value) == t._GenericAlias and isinstance(value.__origin__, type) \
        and issubclass(value.__origin__, Property)  # type: ignore

      if not (is_property_instance or is_property_alias):
        continue

      default = getattr(cls, key, _notset)
      if default is not _notset and not isinstance(default, Property):
        raise TypeError(f'Property default value has unexpected type {type(default)!r}')

      props[key] = Property(None) if default is _notset else default

    setattr(cls, cache_key, props)
    return props

  def get_props(self) -> t.Dict[str, Property]:
    return {k: getattr(self, k) for k in self.get_props_defaults()}

  @overrides
  def _set_property_value(self, name: str, value: t.Any) -> None:
    prop = getattr(self, name)
    if not isinstance(prop, Property):
      raise AttributeError(name)
    prop.set(value)


def visit_properties(provider: Provider, func: t.Callable[[Property], bool]) -> None:
  """
  Visits all #Property instances found in the chain of the specified *provider*. If the *func*
  returns #False, the visitor will not continue the chain down recursively on the current
  property.
  """

  check_instance_of(provider, Provider)

  def _wrapper(prov: Provider) -> bool:
    if isinstance(prov, Property):
      return func(prov)
    return True

  provider.visit(_wrapper)


def collect_properties(provider: Provider) -> t.List[Property]:
  """
  Collects a list of all #Property objects in the chain of the specified *provider*.
  """

  result: t.List[Property] = []
  visit_properties(provider, lambda p: result.append(p) or True)  # type: ignore
  return result
