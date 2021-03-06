#!/usr/bin/env python

import re
import os
import io
import sys
import requests
import argparse
import json
from bs4 import BeautifulSoup
from libs import hls

VERSION = "1.1.9"

def progress(pct):
    sys.stdout.write("\rProgress: {}%".format(pct))
    sys.stdout.flush()


def error(message):
    print("Error: {}".format(message))


def get_req(url, headers = None):
    try:
        req = requests.get(url, headers = headers)
    except requests.exceptions.MissingSchema:
        req = get_req("https://{}".format(url), headers)
    except requests.exceptions.RequestException as e:
        error(e)
        req = None
    return req


def create_filename_base(title):
    basename = re.sub('[/\\\?%\*:|"<>]', '_', title)
    if os.path.isfile(u'{}.ts'.format(basename)):
        i = 1
        while os.path.isfile(u'{} ({}).ts'.format(basename, i)):
            i += 1
        basename = u'{} ({})'.format(basename, i)
    return basename


def nrk_vtt_to_srt(vtt):
    vtt_cues = re.split('\r?\n\r?\n', vtt)[1:]  # First block is 'WEBVTT' and headers
    srt_cues = []
    for cue in vtt_cues:
        cue_lines = cue.splitlines()
        cue_lines[1] = cue_lines[1].replace('.', ',')
        srt_cues.append('\n'.join(cue_lines))
    return '\n\n'.join(srt_cues)


def save_subtitles(subtitles_url, filename):
    print(u"Saving {}".format(filename))
    vtt_req = get_req(subtitles_url)
    vtt_req.encoding = 'utf-8'
    srt = nrk_vtt_to_srt(vtt_req.text)

    with io.open(filename, 'w') as f:
        f.write(srt)


def save_file(url, filename):
    with requests.get(url, stream = True) as req:
        file_size = int(req.headers["Content-Length"])
        chunk_size = 5120
        with open(filename, 'wb') as f:
            for i, chunk in enumerate(req.iter_content(chunk_size = chunk_size)):
                progress(round(100 * chunk_size * i / file_size))
                f.write(chunk)


def save_stream(meta, output_file):
    print(u"Found {}".format(meta['title']))
    filename_base = output_file if output_file else create_filename_base(meta['title'])

    if meta['subtitles']:
        save_subtitles(meta['subtitles'], u'{}.srt'.format(filename_base))

    if meta['stream'].endswith('.mp3'):
        print(u"Saving {}.mp3\n".format(filename_base))
        save_file(meta['stream'], u'{}.mp3'.format(filename_base))
    else:
        print(u"Saving {}.ts\n".format(filename_base))
        hls.dump(meta['stream'], u'{}.ts'.format(filename_base), progress)


def get_meta(program_id):
    metadata = get_req('https://psapi.nrk.no/playback/metadata/{}'.format(program_id)).json()
    manifest = get_req('https://psapi.nrk.no/playback/manifest/{}'.format(program_id)).json()
    if 'message' in metadata:
        error(metadata['message'])
        return None
    try:
        subtitles = manifest['playable']['subtitles'][0]['webVtt']
    except IndexError:
        subtitles = False
    # The subtitle field is sometimes identical to the description field. In
    # these cases, it is very likely correct to drop the subtitle from the
    # title.
    return {'title': ' '.join([s for s in metadata['preplay']['titles'].values() if s and s != metadata['preplay']['description']]),
            'subtitles': subtitles,
            'stream': manifest['playable']['assets'][0]['url']}


def download(program_id, output_file):
    if type(program_id) == list:
        any(download(id) for id in program_id)
    else:
        meta = get_meta(program_id)
        if meta != None:
            save_stream(meta, output_file)
        print('\n')


def get_program_id_from_html(url):
    # Returns None if not found in html
    req = get_req(url)
    if not req:
        return None
    soup = BeautifulSoup(req.text, 'lxml')
    # ID inside Meta tag
    meta_element = soup.find('meta', {'property': 'nrk:program-id'})
    if meta_element:
        return meta_element.get('content')
    # ID inside Section element
    section_element = soup.find('section', {'id': 'program-info'})
    if section_element:
        return section_element.get('data-ga-from-id')
    # ID inside JSON script tag
    json_element = soup.find('script', {'type': 'application/ld+json'})
    if json_element:
        program_id = json.loads(json_element.string).get('@id')
        if program_id:
            return program_id
    # NRK Super
    div_element = soup.find('div', {'data-nrk-id': True})
    if div_element:
        return div_element.get('data-nrk-id')
    # Articles with videos, return list of program ids
    figures = soup.findAll('figure', {'data-video-id': True})
    if figures:
        return [figure.get('data-video-id') for figure in figures]
    # At last try to extract the URL self reference from the HTML
    # and try to extract ID from that as a string
    meta_url = soup.find('meta', {'property': 'og:url'})
    if meta_url:
        return get_program_id_from_string(meta_url.get('content'))
    # Could not find anything
    return None


def get_program_id_from_media_id(media_id):
    req = get_req('https://mimir.nrk.no/plugin/1.0/static?mediaId={}'.format(media_id))
    if not req:
        program_id = None
    else:
        soup = BeautifulSoup(req.text, 'lxml')
        json_info = json.loads(soup.script.get_text())
        program_id = json_info.get('activeMedia', {}).get('psId')
    return program_id


def get_program_id_from_string(program):
    program_id_match = (re.search("(^|/)([A-Z]{4}\d{8})($|/)", program) or
                        re.search("(^|/)PS\*([\da-f-]+)($|/)", program) or
                        re.search("(^|/)(l_[\da-f-]+)($|/)", program))
    media_id_match = re.search("(^|mediaId=)([0-9]+)($|&)", program)
    if program_id_match:
        return program_id_match.group(2)
    elif media_id_match:
        return get_program_id_from_media_id(media_id_match.group(2))
    return None


def get_program_id(program):
    program_id = get_program_id_from_string(program)
    if program_id:
        return program_id
    else:
        return get_program_id_from_html(program)


def main(programs, output_file):
    print("NRK Download {}\n".format(VERSION))
    for i, program in enumerate(programs):
        print(u"Downloading {} of {}:".format(i+1, len(programs)))
        program_id = get_program_id(program)
        if program_id:
            download(program_id, output_file)
        else:
            error(u"Could not parse program ID from '{}'".format(program))


def get_argument_parser():
    parser = argparse.ArgumentParser(description='Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).')
    parser.add_argument("-o", "--output", help="Output file name without extension. Take care if used with multiple PROGRAMS arguments.")
    parser.add_argument("PROGRAMS", nargs="+", help="A list of URLs or program IDs to download")
    return parser


if __name__ == "__main__":
    programs = get_argument_parser().parse_args().PROGRAMS
    output_file = get_argument_parser().parse_args().output
    try:
        main(programs, output_file)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting.\n")
