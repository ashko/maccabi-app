"""Tests for the JSON file store."""

from __future__ import annotations

from ridecoach.models import Category
from ridecoach.storage import Store


def test_seeds_sample_on_first_run(tmp_path):
    store = Store(tmp_path / "data.json")
    assert (tmp_path / "data.json").exists()
    assert len(store.trainees) == 6
    assert len(store.fixed) == 3
    assert len(store.flexible) == 6


def test_round_trip_preserves_everything(tmp_path):
    path = tmp_path / "data.json"
    a = Store(path)
    a.trainer.buffer_min = 22
    a.save()

    b = Store(path)
    assert b.trainer.buffer_min == 22
    assert [t.id for t in b.trainees] == [t.id for t in a.trainees]
    assert [f.label for f in b.fixed] == [f.label for f in a.fixed]
    # session -> trainee references resolve back to real trainee objects
    assert all(f.trainee in b.trainees for f in b.fixed)
    assert b.flexible[0].category in set(Category)
    assert b.flexible[0].availability  # windows survived


def test_next_trainee_id_is_unique(tmp_path):
    store = Store(tmp_path / "data.json")
    new_id = store.next_trainee_id()
    assert new_id not in {t.id for t in store.trainees}
