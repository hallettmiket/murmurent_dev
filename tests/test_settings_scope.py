"""Every dashboard setting has a recorded scope (#187).

Adding a field to a settings window without deciding whether it belongs to
this machine, to the person, or to the lab fails here. Register it in
src/murmurent/core/settings_scope.py.
"""

from __future__ import annotations

import pytest

from murmurent.core import settings_scope as ss
from murmurent.dashboard import contract as C
from murmurent.dashboard import server as S


@pytest.mark.parametrize("window, model", [
    ("profile", S.MemberSettingsBody),
    ("profile", C.MemberSettings),
    ("machine", S.MachineSettingsBody),
    ("machine", C.MachineSettings),
    ("lab", S.LabSettingsBody),
])
def test_every_field_has_a_scope(window, model):
    missing = [f for f in model.model_fields if ss.scope_of(window, f) is None]
    assert not missing, f"{window} window: no scope recorded for {missing}"


def test_scopes_are_known():
    allowed = {ss.MACHINE, ss.PERSON, ss.LAB, ss.PERSON_PER_MACHINE}
    assert {scope for scope, _ in ss.REGISTER.values()} <= allowed
