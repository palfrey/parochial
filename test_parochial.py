import pytest
from .parochial import ShortListStore
from coherence.base import Coherence, Plugins
from twisted.internet import defer
from pytest_twisted import init_default_reactor


@pytest.mark.vcr()
def test_init():
    server = object()
    ShortListStore(server)


@pytest.mark.vcr()
def test_upnpinit():
    init_default_reactor()
    Plugins().set("ShortListStore", ShortListStore)
    Coherence(
        config={
            "logging": {"subsystem": []},
            "plugin": [
                {
                    "backend": "ShortListStore",
                    "name": "foo",
                    "medialocation": "bar",
                    "mediadb": "bar.db",
                    "trackcount": 0,
                    "updateFrequency": 30,
                },
            ],
            "serverport": 10235,
        }
    )
    d1 = defer.Deferred()
    return d1
    # reactor.run()
