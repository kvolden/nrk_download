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

VERSION = "1.1.6"

# Currently not clear if API-key is needed
API_KEY = ''

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
    srt = nrk_vtt_to_srt(vtt_req.text)

    with io.open(filename, 'w') as f:
        f.write(srt)


def save_stream(meta):
    print(u"Found {}".format(meta['title']))
    filename_base = create_filename_base(meta['title'])

    if meta['subtitles']:
        save_subtitles(meta['subtitles'], u'{}.srt'.format(filename_base))

    print(u"Saving {}.ts\n".format(filename_base))
    hls.dump(meta['stream'], u'{}.ts'.format(filename_base), progress)


def get_meta(program_id):
    metadata = get_req('https://psapi.nrk.no/mediaelement/{}?apiKey={}'.format(program_id, API_KEY)).json()
    manifest = get_req('https://psapi.nrk.no/playback/manifest/{}?apiKey={}'.format(program_id, API_KEY)).json()
    if 'message' in metadata:
        error(metadata['message'])
        return None
    try:
        subtitles = manifest['playable']['subtitles'][0]['webVtt']
    except IndexError:
        subtitles = False
    return {'title': metadata['fullTitle'],
            'subtitles': subtitles,
            'stream': manifest['playable']['assets'][0]['url']}


def download(program_id):
    if type(program_id) == list:
        any(download(id) for id in program_id)
    else:
        meta = get_meta(program_id)
        if meta != None:
            save_stream(meta)
        print('\n')


def get_program_id_from_html(url):
    # Returns None if not found in html
    req = get_req(url)
    if not req:
        return None
    soup = BeautifulSoup(req.text, 'lxml')
    # Standard player
    section_element = soup.find('section', {'id': 'program-info'})
    if section_element:
        return section_element.get('data-ga-from-id')
    # New series player
    json_element = soup.find('script', {'type': 'application/ld+json'})
    if json_element:
        return json.loads(json_element.get_text()).get('@id')
    # NRK Super
    div_element = soup.find('div', {'data-nrk-id': True})
    if div_element:
        return div_element.get('data-nrk-id')
    # Articles with videos, return list of program ids
    figures = soup.findAll('figure', {'data-video-id': True})
    if figures:
        return [figure.get('data-video-id') for figure in figures]
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


def get_program_id(passed_string):
    # Extract program ID from string:
    program_id_match = (re.search("(^|/)([A-Z]{4}\d{8})($|/)", passed_string) or
                        re.search("(^|/)PS\*([\da-f-]+)($|/)", passed_string))
    if program_id_match:
        program_id = program_id_match.group(2)
    else:
        # nrk.no/skole style mediaId:
        media_id_match = re.search("(^|mediaId=)([0-9]+)($|&)", passed_string)
        if media_id_match:
            program_id = get_program_id_from_media_id(media_id_match.group(2))
        else:
            program_id = get_program_id_from_html(passed_string)
    return program_id


def main(programs):
    print("NRK Download {}\n".format(VERSION))
    for i, program in enumerate(programs):
        print(u"Downloading {} of {}:".format(i+1, len(programs)))
        program_id = get_program_id(program)
        if program_id:
            download(program_id)
        else:
            error(u"Could not parse program ID from '{}'".format(program))


def get_argument_parser():
    parser = argparse.ArgumentParser(description='Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).')
    parser.add_argument("PROGRAMS", type=str, nargs="+", help="A list of URLs or program IDs to download")
    return parser


if __name__ == "__main__":
    programs = get_argument_parser().parse_args().PROGRAMS
    try:
        main(programs)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting.\n")
