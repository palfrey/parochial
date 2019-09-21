from __future__ import print_function
from twisted.internet import reactor
from coherence.base import Coherence, Plugins
from coherence.backend import BackendItem, BackendStore
from coherence.backends.mediadb_storage import MediaStore, Track, KNOWN_AUDIO_TYPES
from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, AudioItem
from twisted.python.filepath import FilePath
import coherence.extern.louie as louie

import logging
import random
import os.path
import re

NUMS = re.compile('([0-9]+)')

def _natural_key(s):
    # strip the spaces
    s = s.get_name().strip()
    # <class 'TypeError'>: '<' not supported between instances of 'int' and 'str'
    return [part.isdigit() and part or part.lower() for part in
            NUMS.split(s)]

class ShortListItem(BackendItem):
    logCategory = 'shortlist_item'

    def __init__(self, object_id, parent, path, mimetype, urlbase, UPnPClass,
                 update=False, store=None):
        BackendItem.__init__(self)
        self.id = object_id

        if mimetype == 'root':
            self.update_id = 0
        if mimetype == 'item' and path is None:
            path = os.path.join(parent.get_realpath(), str(self.id))
        self.location = path
        self.debug("location %s", self.location)
        self.mimetype = mimetype
        if urlbase[-1] != '/':
            urlbase += '/'
        self.url = urlbase + str(self.id)
        if parent is None:
            parent_id = -1
        else:
            parent_id = parent.get_id()
        self.item = UPnPClass(object_id, parent_id, self.get_name())
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = []
        self.sorted = False

    def get_id(self):
        return self.id

    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update:
            self.update_id += 1
        self.sorted = False

    def get_name(self):
        if hasattr(self, "display"):
            return self.display
        if isinstance(self.location, FilePath):
            return self.location.basename()
        else:
            return self.location

    def get_children(self, start=0, request_count=0):
        try:
            if not self.sorted:
                self.children.sort(key=_natural_key)
                self.sorted = True
            if request_count == 0:
                return self.children[start:]
            else:
                return self.children[start:request_count]
        except Exception as e:
            self.error(e)
            raise

    def get_child_count(self):
        self.debug("get_child_count")
        return self.child_count

    def __getattr__(self, key):
        #print("get item", key)
        return super.__getattr__(self, key)

    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + \
               str(self.get_name().encode('ascii', 'xmlcharrefreplace')) if self.get_name() != None else ''

class ShortListStore(BackendStore):
    logCategory = 'shortlist_store'

    implements = ['MediaServer']

    description = '''MediaServer exporting files from the file-system'''

    options = [
        {'option': 'name', 'type': 'string', 'default': 'my media',
         'help': 'the name under this MediaServer '
                 'shall show up with on other UPnP clients'},
        {'option': 'source_backend', 'type': 'uuid',
         'help': 'other backend to use as raw source'},
    ]

    coherences = {}
    source_backends = {}

    def __init__(self, server, source_backend=None, **kwargs):
        BackendStore.__init__(self, server, **kwargs)
        self.name = kwargs.get('name', 'ShortlistStore')
        self.next_id = 1000
        self.store = {}
        UPnPClass = classChooser('root')
        id = str(self.getnextID())
        self.root = ShortListItem(
            id, None, 'media', 'root',
            self.urlbase, UPnPClass, update=True, store=self)
        self.add_store_item(id, self.root)

        self.source_backend = MediaStore(server, **kwargs)

        self.wmc_mapping.update({'14': '0',
                                 '15': '0',
                                 '16': '0',
                                 '17': '0'
                                 })
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def __repr__(self):
        return self.__class__.__name__

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def get_by_id(self, id):
        self.debug("Get by id: %s" % id)
        if id == '0':
            id = '1000'
        try:
            return self.store[id]
        except KeyError:
            self.info("Nothing for %s", id)
            self.debug(self.store.keys())
            return None

    def add_store_item(self, id, item):
        if id in self.store:
            raise Exception("Already have %s in store" % id)
        self.store[id] = item
        return self.store[id]

    def make_playlist(self):
        self.debug("Source backend %s", self.source_backend)
        keys = list(self.source_backend.db.query(Track, sort=Track.title.ascending))
        for x in range(50):
            while True:
                if len(keys) == 0:
                    break
                item = random.choice(keys)
                self.debug("theirs: %s %s", item.__dict__, item.get_id())
                _, ext = os.path.splitext(item.location)
                id = self.getnextID()
                id = str(id)

                try:
                    mimetype = KNOWN_AUDIO_TYPES[ext]
                except KeyError:
                    mimetype = 'audio/mpeg'

                entry = self.add_store_item(id, ShortListItem(
                            id, self.root, item.location, mimetype,
                            self.urlbase, classChooser(mimetype), update=True, store=self))
                
                entry.item = item.get_item()
                entry.item.title = "%s - %s" % (item.album.artist.name, item.title)

                _, ext = os.path.splitext(item.location)
                self.debug("mine %s %s %s", entry, entry.item.__dict__, entry.item.res[0].__dict__)
                self.add_store_item(str(item.get_id()) + ext, entry)

                self.root.add_child(entry)
                self.root.update_id +=1
                keys.remove(item)
                break
            if len(keys) == 0:
                break
        #self.debug("children: %s", self.root.children)

    def upnp_init(self):
        self.source_backend.upnp_init()
        self.debug("upnp_init %s", self.server)
        self.make_playlist()
        #self.debug(self.store)
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(
                0,
                'SourceProtocolInfo',
                ['internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                 'http-get:*:audio/mpeg:*',
                 'internal:%s:application/ogg:*' % self.server.coherence.hostname,  # noqa
                 'http-get:*:application/ogg:*',
                 ],
                default=True)
            self.server.content_directory_server.set_variable(
                0, 'SystemUpdateID', self.update_id)
            self.server.content_directory_server.set_variable(
                0, 'SortCapabilities', '*')

Plugins().set("ShortListStore", ShortListStore)

coherence = Coherence(
    {'logmode': 'warning',
     'controlpoint': 'yes',
     'interface': 'en0',
     'plugin': [
          {'backend': 'ShortListStore',
          'name': 'Shortlist',
          'medialocation': '/Users/palfrey/Dropbox/Music/R.E.M',
          'mediadb': 'test.db'},
      ]
     }
)

reactor.run()