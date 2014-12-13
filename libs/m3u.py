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
from collections import namedtuple
import re
import requests
import sys
if sys.version_info > (3,):
    from urllib.parse import urljoin
else:
    from urlparse import urljoin

CSV_PATTERN = re.compile(r'''((?:[^,"' ]|"[^"]*"|'[^']*')+)''')
INF_DIRECTIVE = '#EXTINF:'
STREAM_DIRECTIVE = '#EXT-X-STREAM-INF:'
KEY_DIRECTIVE = '#EXT-X-KEY:'

MediaInfo = namedtuple('MediaInfo', 'sequence, target_duration, is_encrypted, key_url, iv')
VariantInfo = namedtuple('VariantInfo', 'url, bandwidth')


def is_m3u(playlist):
    return playlist.split('\n', 1)[0].strip() == "#EXTM3U"


def is_encrypted(playlist):
    return KEY_DIRECTIVE in playlist


def is_master(playlist):
    for line in playlist.splitlines():
        if line.startswith(STREAM_DIRECTIVE):
            return True
        if line.startswith(INF_DIRECTIVE):
            return False
    return False


def get_variants(url, playlist):
    assert is_master(playlist)
    playlist = iter(playlist.splitlines())
    variants = []
    for line in playlist:
        if line.startswith(STREAM_DIRECTIVE):
            line = line.split(STREAM_DIRECTIVE)[1]
            info = _attr_list(line)
            stream_url = urljoin(url, next(playlist))
            bw = int(info['BANDWIDTH'])
            variants.append(VariantInfo(stream_url, bw))
    return variants


def get_segments(url, playlist):
    playlist = iter(playlist.splitlines())
    segment_urls = []
    for line in playlist:
        if line.startswith(INF_DIRECTIVE):
            line = line.split(INF_DIRECTIVE)[1]
            segment_urls.append(urljoin(url, next(playlist)))
    return segment_urls


def get_media_info(playlist):
    playlist = iter(playlist.splitlines())
    sequence = 0
    target_duration = 0
    method = None
    key_url = None
    iv = None
    for line in playlist:
        if line.startswith('#EXT-X-TARGETDURATION:'):
            target_duration = int(line.split('#EXT-X-TARGETDURATION:')[1])
        elif line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
            sequence = int(line.split('#EXT-X-MEDIA-SEQUENCE:')[1])
        elif line.startswith(KEY_DIRECTIVE):
            attrs = _attr_list(line.split(KEY_DIRECTIVE)[1])
            if attrs['METHOD'] != 'NONE':
                method = attrs['METHOD']
                key_url = attrs['URI']
                if 'IV' in attrs:
                    iv = binascii.unhexlify(attrs['IV'][2:])
        elif line.startswith(INF_DIRECTIVE):
            break
    return MediaInfo(sequence, target_duration, bool(method), key_url, iv)


def _attr_list(s):
    attributes = CSV_PATTERN.split(s)[1::2]
    info = {}
    for attr in attributes:
        field, value = tuple(attr.split("=", 1))
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        info[field] = value
    return info
