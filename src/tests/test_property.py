
import typing as t

import pytest

from kahmi.build.model.property import HavingProperties, ListProperty, NoValuePresent, Property, collect_properties


def test_empty_property():
  prop = Property[int]()

  assert not prop
  assert prop.or_none() is None
  assert prop.or_else(42) == 42
  with pytest.raises(NoValuePresent):
    prop.get()


def test_filled_property():
  prop = Property[int](0)

  assert prop
  assert prop.or_none() == 0
  assert prop.or_else(42) == 0
  assert prop.get() == 0


def test_property_set():
  prop = Property[int]()
  prop.set(42)

  assert prop
  assert prop.get() == 42


def test_property_lazy_eval():
  prop1 = Property[int](42)
  prop2 = Property[int](prop1.map(lambda v: v * 2))

  assert prop2.get() == 84

  prop1.set(10)

  assert prop2.get() == 20


def test_property_finalize():
  prop1 = Property[int](42)
  prop2 = Property[int](prop1.map(lambda v: v * 2))
  prop2.finalize()
  prop1.set(1)

  assert prop2.get() == 84


def test_property_finalize_on_read():
  prop1 = Property[int](42)
  prop2 = Property[int](prop1.map(lambda v: v * 2))
  prop2.finalize_on_read()
  prop1.set(1)

  assert prop2.get() == 2

  prop1.set(10)

  assert prop2.get() == 2


def test_property_map():
  prop = Property[str]('foo')
  assert prop.map(lambda v: v + 'bar').or_none() == 'foobar'

  prop = Property[str](None)
  assert prop.map(lambda v: v + 'bar').or_none() is None


def test_property_flatmap():
  prop = Property[str]('foo')
  assert prop.flatmap(lambda v: Property(v + 'bar')).or_none() == 'foobar'

  prop = Property[str](None)
  assert prop.flatmap(lambda v: Property(v + 'bar')).or_none() is None


def test_property_coalesce():
  prop1 = Property[str](None)
  prop2 = Property[str]('foo')
  prop3 = Property[str]('bar')
  assert prop1.coalesce(prop2).or_none() == 'foo'
  assert prop3.coalesce(prop2).or_none() == 'bar'


def test_having_properties_constructor():

  class MyClass(HavingProperties):
    prop1: Property[int]
    prop2: Property[t.List[str]]
    prop3: Property[t.Set[str]] = Property({'a', 'b'})
    prop4: int = 42

  obj = MyClass()

  assert obj.prop1.or_none() is None
  assert obj.prop2.or_none() is None
  assert obj.prop3.or_none() == {'a', 'b'}

  assert obj.prop1.name == 'prop1'
  assert obj.prop1.origin is obj

  assert obj.get_props().keys() == {'prop1', 'prop2', 'prop3'}

  assert MyClass.prop3.set({'foo', 'bar'})
  assert obj.prop3.get() == {'foo', 'bar'}


def test_collect_properties():
  p1 = Property[int](3, name='p1')
  p2 = p1.map(lambda v: v + 2)
  p3 = Property[int](10, name='p3')
  p4 = Property[int](name='empty').coalesce(p2).flatmap(lambda v: Property(p3.get() + v))

  assert p4.get() == 15
  assert [x.name for x in collect_properties(p4)] == ['empty', 'p1', 'p3']


def test_property_instantiation_inherits_markers():
  my_marker = object()

  class MyClass(HavingProperties):
    props: Property[int] = Property(None, my_marker)

  assert MyClass().props.markers == [my_marker]


def test_list_property():
  lp = ListProperty[str]()
  lp.add('hello')
  lp.extend(['world', Property[str]('!')])
  assert lp.get() == ['hello', 'world', '!']
