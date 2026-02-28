from django.forms import formset_factory
from homeworks.forms import SectionForm, SectionFormSet

SectionFormset = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
assert issubclass(SectionFormset, SectionFormSet)
section_formset: SectionFormSet = SectionFormset(prefix="sections")
