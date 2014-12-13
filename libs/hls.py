"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import binascii
import m3u
import os
import requests


def dump(url, filename, progress_cb=None, abort_cb=None, max_bandwidth=float('inf')):
    aborted = False
    with open(filename, 'wb') as out:
        strm = get_stream(url, max_bandwidth)
        fetched = 0
        for chunk in strm.iter_content():
            if abort_cb and abort_cb():
                aborted = True
                break
            fetched += len(chunk)
            if progress_cb:
                p = int(fetched / float(strm.estimated_size) * 100)
                progress_cb(p)
            out.write(chunk)
    if aborted:
        os.remove(filename)


def get_stream(url, max_bandwidth=float('inf')):
    session = requests.Session()
    r = session.get(url)
    r.raise_for_status()
    playlist = r.text
    if m3u.is_master(playlist):
        streams = m3u.get_variants(url, playlist)
        url = select_stream(streams, max_bandwidth).url
        r = session.get(url)
        r.raise_for_status()
        playlist = r.text
    return MediaStream(url, playlist)


def select_stream(streams, max_bandwidth=float('inf')):
    assert len(streams) > 0
    selected = streams[0]
    for stream in streams[1:]:
        if selected.bandwidth < stream.bandwidth <= max_bandwidth:
            selected = stream
    return selected


def _get_playlist(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.text


class MediaStream(object):
    def __init__(self, url, _playlist=None):
        playlist = _playlist or _get_playlist(url)
        assert m3u.is_m3u(playlist)
        assert not m3u.is_master(playlist)
        info = m3u.get_media_info(playlist)
        self.sequence = info.sequence
        self.is_encrypted = info.is_encrypted
        self.iv = info.iv
        self.key = None
        if self.is_encrypted:
            r = requests.get(info.key_url)
            r.raise_for_status()
            self.key = r.content
        self.segment_urls = m3u.get_segments(url, playlist)
        self.estimated_size = 0
    
    def _iter_content_direct(self, chunk_size=128):
        def gen():
            size = SizeEstimator(self)
            for url in self.segment_urls:
                r = requests.get(url, stream=True)
                r.raise_for_status()
                size.update(r)
                for chunk in r.iter_content(chunk_size):
                    yield chunk
            size.final()
        return gen()
    
    def iter_content(self, chunk_size=128):
        if not self.is_encrypted:
            return self._iter_content_direct(chunk_size)
        
        from Crypto.Cipher import AES
        unpad = lambda s: s[0:-ord(s[-1])]
        def gen():
            size = SizeEstimator(self)
            for i, url in enumerate(self.segment_urls):
                req = requests.get(url, stream=True)
                req.raise_for_status()
                size.update(req)
                iv = self.iv or binascii.unhexlify(('0x%032x' % (self.sequence + i))[2:])
                cipher = AES.new(self.key, AES.MODE_CBC, iv)
                while True:
                    chunk = req.raw.read(chunk_size)
                    if not chunk:
                        break
                    chunk = cipher.decrypt(chunk)
                    if req.raw.closed:
                        # end of segment
                        yield unpad(chunk)
                        break
                    yield chunk
                size.final()
        return gen()


class SizeEstimator(object):
    def __init__(self, stream):
        self.i = 0
        self.fetched = 0
        self.stream = stream
        self.num_segments = len(stream.segment_urls)
    
    def update(self, segment_req):
        self.i += 1
        segment_size = int(segment_req.headers['content-length'])
        self.fetched += segment_size
        avg_segment_size = int(self.fetched / float(self.i))
        self.stream.estimated_size = avg_segment_size * self.num_segments
    
    def final(self):
        self.stream.estimated_size = self.fetched
