from twisted.internet import reactor
from coherence.base import Coherence, Plugins
from coherence.backend import BackendItem, BackendStore
from coherence.backends.fs_storage import FSStore
from coherence.log import get_logger, loggers
from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, AudioItem
from twisted.python.filepath import FilePath

import logging
import random
import os.path

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
        self.location = FilePath(path)
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
        if isinstance(self.location, FilePath):
            name = self.location.basename()
        else:
            name = self.location
        return name

    def get_children(self, start=0, request_count=0):
        print("get_children", self, start, request_count, self.children)
        if not self.sorted:
            self.children.sort(key=_natural_key)
            self.sorted = True
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

    def get_child_count(self):
        print("get_child_count")
        return self.child_count

    def __getattr__(self, key):
        print("get item", key)
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
        self.root = self.store[id] = ShortListItem(
            id, None, 'media', 'root',
            self.urlbase, UPnPClass, update=True, store=self)

        self.source_backend = FSStore(None, **kwargs)

        self.wmc_mapping.update({'14': '0',
                                 '15': '0',
                                 '16': '0',
                                 '17': '0'
                                 })
        self.make_playlist()
        print(self.store)
        self.init_completed = True

    def __repr__(self):
        return self.__class__.__name__

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def __getattr__(self, key):
        print("get store", key)
        return super.__getattr__(self, key)

    def get_by_id(self, id):
        print("Get by id", id)
        if id == '0':
            id = '1000'
        try:
            return self.store[id]
        except KeyError:
            return None
    
    def make_playlist(self):
        print("Source backend", self.source_backend)
        keys = list(self.source_backend.store.keys())
        for x in range(5):
            while True:
                key = random.choice(keys)
                item = self.source_backend.store[key]
                if type(item.item) != AudioItem:
                    continue
                print("theirs", item, item.item, item.item.res[0].__dict__)
                _, ext = os.path.splitext(item.url)
                id = self.getnextID()
                id = str(id) + ext.lower()
                self.store[id] = ShortListItem(
                            id, self.root, item.url, item.mimetype,
                            self.urlbase, classChooser(item.mimetype), update=True, store=self)
                self.store[id].item.res = item.item.res
                print("mine", self.store[id], self.store[id].item, self.store[id].item.res[0].__dict__)
                print(dir(self.store[id]))
                self.root.add_child(self.store[id])
                self.root.update_id +=1
                break
        print("children", self.root.children)

    def upnp_init(self):
        print("upnp_init", self.server)
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(
                0,
                'SourceProtocolInfo',
                [f'internal:{self.server.coherence.hostname}:audio/mpeg:*',
                 'http-get:*:audio/mpeg:*',
                 f'internal:{self.server.coherence.hostname}:video/mp4:*',
                 'http-get:*:video/mp4:*',
                 f'internal:{self.server.coherence.hostname}:application/ogg:*',  # noqa
                 'http-get:*:application/ogg:*',
                 f'internal:{self.server.coherence.hostname}:video/x-msvideo:*',  # noqa
                 'http-get:*:video/x-msvideo:*',
                 f'internal:{self.server.coherence.hostname}:video/mpeg:*',
                 'http-get:*:video/mpeg:*',
                 f'internal:{self.server.coherence.hostname}:video/avi:*',
                 'http-get:*:video/avi:*',
                 f'internal:{self.server.coherence.hostname}:video/divx:*',
                 'http-get:*:video/divx:*',
                 f'internal:{self.server.coherence.hostname}:video/quicktime:*',  # noqa
                 'http-get:*:video/quicktime:*',
                 f'internal:{self.server.coherence.hostname}:image/gif:*',
                 'http-get:*:image/gif:*',
                 f'internal:{self.server.coherence.hostname}:image/jpeg:*',
                 'http-get:*:image/jpeg:*'
                 # 'http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=11;'
                 # 'DLNA.ORG_FLAGS=01700000000000000000000000000000',
                 # 'http-get:*:audio/x-ms-wma:DLNA.ORG_PN=WMABASE;'
                 # 'DLNA.ORG_OP=11;DLNA.ORG_FLAGS'
                 # '=01700000000000000000000000000000',
                 # 'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=00f00000000000000000000000000000',
                 # 'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_SM;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=00f00000000000000000000000000000',
                 # 'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_MED;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=00f00000000000000000000000000000',
                 # 'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=00f00000000000000000000000000000',
                 # 'http-get:*:video/mpeg:DLNA.ORG_PN=MPEG_PS_PAL;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=01700000000000000000000000000000',
                 # 'http-get:*:video/x-ms-wmv:DLNA.ORG_PN=WMVMED_BASE;'
                 # 'DLNA.ORG_OP=01;DLNA.ORG_FLAGS'
                 # '=01700000000000000000000000000000',
                 ],
                default=True)
            self.server.content_directory_server.set_variable(
                0, 'SystemUpdateID', self.update_id)
            # self.server.content_directory_server.set_variable(
            #     0, 'SortCapabilities', '*')

Plugins().set("ShortListStore", ShortListStore)

coherence = Coherence(
    {'logmode': 'warning',
     'controlpoint': 'yes',
     'plugin': [
          {'backend': 'ShortListStore',
          'name': 'Shortlist',
          'content': '/Users/palfrey/Dropbox/Music/Kittie'}
     ]
     }
)

reactor.run()