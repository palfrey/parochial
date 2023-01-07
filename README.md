Parochial
=========

Parochial is a tool based on top of [Coherence](https://github.com/opacam/Cohen3) to provide limited-length playlists to workaround bugs in some DLNA radios, primarily around limits on the number of tracks they can randomly shuffle. The playlists are randomly chosen from all your music tracks, and will periodically cycle the playlist so there's always something new.

Usage
-----

1. Get a copy of this repository
2. `pip install -r requirements.txt`
3. `python parochial.py --help` to see the options. You'll need at least `-m <path to your music files>`

The music database uses the Coherence MediaStore behind the scenes, which unfortunately doesn't currently update the database ever. If there's no database file to begin with, it'll create it but AFAIK there's [no update mechanism](https://github.com/palfrey/parochial/issues/3).
