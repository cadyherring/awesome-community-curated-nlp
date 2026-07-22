import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evidence_app.core.db import connect  # noqa: E402


@pytest.fixture
def con(tmp_path):
    connection = connect(tmp_path / "evidence.sqlite3")
    yield connection
    connection.close()


@pytest.fixture
def store_root(tmp_path):
    return tmp_path / "store"


@pytest.fixture
def sample_dir(tmp_path):
    d = tmp_path / "sample"
    d.mkdir()
    return d
