from typing import Type

class Base: pass
class Derived(Base): pass

def factory() -> Type[Base]: return Derived

def take_derived(d: Derived): pass

def test():
    Cls = factory()
    assert issubclass(Cls, Derived)
    instance = Cls()
    take_derived(instance)
