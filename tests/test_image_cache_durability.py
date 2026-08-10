"""Enhanced-image cache must only ever store durable URLs.

Render declares no disk for this service, so `data/images/` is wiped on every
deploy. The DB cache used to store "/static/images/enhanced/<hash>.png" — a
pointer INTO that ephemeral disk. The row survived the deploy, the file did
not, so the cache reported a HIT, served a dead URL, and suppressed
regeneration. Strictly worse than no cache.
"""

import pytest

from ospra_os.api.image_generation_routes import (
    _is_durable_image_url,
    get_cached_enhanced_image,
    save_enhanced_image_to_cache,
)


@pytest.mark.parametrize("url", [
    "https://res.cloudinary.com/x/image/upload/v1/ospra/enhanced/abc.png",
    "http://cdn.example.test/a.png",
])
def test_absolute_urls_are_durable(url):
    assert _is_durable_image_url(url) is True


@pytest.mark.parametrize("url", [
    "/static/images/enhanced/abc123.png",
    "data/images/enhanced/abc123.png",
    "",
    None,
])
def test_ephemeral_paths_are_not_durable(url):
    assert _is_durable_image_url(url) is False


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None):
        self._row = row
        self.added = []
        self.deleted = []
        self.commits = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._row)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class _Row:
    def __init__(self, enhanced_url):
        self.enhanced_url = enhanced_url


def test_poisoned_row_is_treated_as_miss_and_dropped():
    """Existing rows written before the rule must self-heal, not serve 404s."""
    db = _FakeDB(row=_Row("/static/images/enhanced/dead.png"))

    result = get_cached_enhanced_image(db, "https://supplier.test/img.jpg")

    assert result is None, "a pointer into ephemeral disk must not be a hit"
    assert len(db.deleted) == 1, "the poisoned row should be removed"


def test_durable_row_is_served():
    cdn = "https://res.cloudinary.com/x/image/upload/v1/enhanced/ok.png"
    db = _FakeDB(row=_Row(cdn))

    assert get_cached_enhanced_image(db, "https://supplier.test/img.jpg") == cdn
    assert db.deleted == []


def test_writing_a_relative_path_is_refused():
    db = _FakeDB()

    save_enhanced_image_to_cache(
        db, "https://supplier.test/img.jpg", "/static/images/enhanced/new.png"
    )

    assert db.added == [], "must not persist a non-durable URL"
    assert db.commits == 0
