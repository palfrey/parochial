from __future__ import print_function
from twisted.internet import reactor
from coherence.base import Coherence, Plugins
from coherence.backend import BackendItem, BackendStore
from coherence.backends.mediadb_storage import MediaStore, Track, KNOWN_AUDIO_TYPES
from coherence.upnp.core.DIDLLite import classChooser, Container, Resource
from twisted.python.filepath import FilePath
import coherence.extern.louie as louie

import random
import os.path
import argparse

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

    def get_id(self):
        return self.id

    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update:
            self.update_id += 1

    def get_name(self):
        if hasattr(self, "display"):
            return self.display
        if isinstance(self.location, FilePath):
            return self.location.basename()
        else:
            return self.location

    def get_children(self, start=0, request_count=0):
        try:
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

    description = '''Subset playlist backend based on a mediadb backend to workaround track limits'''

    options = [
        {'option': 'name', 'type': 'string', 'default': 'ShortlistStore',
         'help': 'the name under this MediaServer '
                 'shall show up with on other UPnP clients'},
        {'option': 'medialocation', 'type': 'string',
         'help': 'path to media'},
        {'option': 'mediadb', 'type': 'string',
         'help': 'path to media database (will be created if doesn\'t exist)'},
        {'option': 'trackcount', 'type': 'integer',
         'help': 'tracks in the playlist', 'default': 50},
    ]

    def __init__(self, server, name="ShortlistStore", trackcount=50, **kwargs):
        BackendStore.__init__(self, server, **kwargs)
        self.name = name
        self.next_id = 1000
        self.store = {}
        self.trackcount = trackcount
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
        for x in range(self.trackcount):
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

                self.debug("mine %s %s %s", entry, entry.item.__dict__, entry.item.res[0].__dict__)
                self.add_store_item(str(item.get_id()) + ext, entry)

                self.root.add_child(entry)
                self.root.update_id +=1
                keys.remove(item)
                break
            if len(keys) == 0:
                break

    def upnp_init(self):
        self.source_backend.upnp_init()
        self.debug("upnp_init %s", self.server)
        self.make_playlist()
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

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--music-path", required=True, help="Path to your music files")
parser.add_argument("-n", "--name", default="Shortlist", help="Name of UPnP store")
parser.add_argument("-d", "--db", default="music.db", help="Path to music database (default: music.db)")
parser.add_argument("-i", "--item-count", default=50, type=int, help="Number of tracks in the playlist (default: 50)")
args = parser.parse_args()

coherence = Coherence(
    {'logmode': 'warning',
     'controlpoint': 'yes',
     'plugin': [
          {
            'backend': 'ShortListStore',
            'name': args.name,
            'medialocation': args.music_path,
            'mediadb': args.db,
            'trackcount': args.item_count
          },
      ]
     }
)

reactor.run()