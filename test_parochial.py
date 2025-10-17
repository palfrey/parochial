import logging
from pathlib import Path
import shutil
import pytest
from .parochial import ShortListStore
from coherence import log
import uuid


class ConnectionManagerServer:
    def set_variable(self, instance, variable_name, value, default=False):
        pass


class ContentDirectoryServer:
    def set_variable(self, instance, variable_name, value, default=False):
        pass


class Coherence:
    hostname = "foo"


class MockServer:
    connection_manager_server = ConnectionManagerServer()
    content_directory_server = ContentDirectoryServer()
    coherence = Coherence()
    uuid = uuid.uuid4()


@pytest.mark.vcr()
def test_init():
    log.init(loglevel=logging.DEBUG)
    server = MockServer()
    test_db_path = Path("/tmp/parochial-test-db")
    if test_db_path.exists():
        shutil.rmtree(test_db_path)
        assert not test_db_path.exists()
    store = ShortListStore(server, medialocation="testdata", mediadb=test_db_path)
    store.source_backend.upnp_init()
    store.upnp_init()
