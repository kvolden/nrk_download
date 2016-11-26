#!/usr/bin/env python

import re
import os
import io
import sys
import requests
import datetime
import argparse
import json
from bs4 import BeautifulSoup
from libs import hls

VERSION = "1.1.2"

TVAPI_BASE_URL = "https://tvapi.nrk.no/v1/programs/{}"
SUBS_BASE_URL = "http://v8.psapi.nrk.no/programs/{}/subtitles/tt"
MIMIR_BASE_URL = "https://mimir.nrk.no/plugin/1.0/static?mediaId={}"

def progress(pct):
    sys.stdout.write("\rProgress: {}%".format(pct))
    sys.stdout.flush()


def error(message):
    print("Error: {}".format(message))

    
def xml2srt(text=''):
    soup = BeautifulSoup(text, "xml")
    result = u''
    zerotime = datetime.datetime.strptime("0", "%H")    # For simple converting to timedelta
    entries_skipped = 0                                 # To maintain continuous index increment even when fail
    prev_end = zerotime                                 # Previous section end time

    for i, p in enumerate(soup("p"), start=1):
        try:                                            # Sometimes malformed with negative duration
            begin = datetime.datetime.strptime(p["begin"], "%H:%M:%S.%f")
            end = begin + (datetime.datetime.strptime(p["dur"], "%H:%M:%S.%f") - zerotime)
        except:
            entries_skipped += 1
            continue

        if begin.hour >= 10:                            # Compensate erroneous 10 hour tape offset
            begin -= datetime.timedelta(hours = 10)
        if begin < prev_end:                            # Prevent overlap
            begin = prev_end

        prev_end = end
        
        section = u"{}\n".format(i - entries_skipped)    # u"" to make sure it's unicode in both python 2.7 and 3
        section += "{},{:03d} --> ".format(begin.strftime("%H:%M:%S"), begin.microsecond/1000)
        section += "{},{:03d}\n".format(end.strftime("%H:%M:%S"), end.microsecond/1000)
        if p.br:
            p.br.replace_with("\n")
        section += p.text
        section = section.strip()
        section = re.sub("[\n]{2,}", "\n", section)
        result += section + "\n\n"
            
    return result


def download(program_id):
    session = requests.Session()
    session.headers["User-Agent"] = ""
    session.headers["app-version-android"] = "999"

    req = session.get(TVAPI_BASE_URL.format(program_id))
    #TODO: Exception handler
    if not req.text:
        error("Empty response from server. Non-existing program ID?")
        return

    response_data = req.json()

    title = response_data["fullTitle"]
    print(u"Found: {}".format(title))

    if "mediaUrl" in response_data:
        media_url = response_data["mediaUrl"]
    else:
        error("Could not find media stream. No longer available?")
        return
    
    filename = re.sub('[/\\\?%\*:|"<>]', '_', title)   # not allowed: / \ ? % * : | " < >

    # Ensure unique filename:
    if os.path.isfile(filename + ".ts"):
        index = 1
        while(os.path.isfile(filename + " ({}).ts".format(index))):
            index += 1
        filename = filename + " ({})".format(index)

    # Save subtitles, if any:
    if response_data["hasSubtitles"]:
        print(u"Saving {}.srt".format(filename))
        subtitles_xml = requests.get(SUBS_BASE_URL.format(program_id)).text
        subtitles_srt = xml2srt(subtitles_xml)
        srtfile = io.open(filename + ".srt", "w")
        srtfile.write(subtitles_srt)
        srtfile.close()

    # Start dumping HLS stream:
    print(u"Saving {}.ts\n".format(filename))
    hls.dump(media_url, filename + ".ts", progress)

    print("\n")


def get_program_id_online(url):
    try:
        req = requests.get(url)
    except requests.exceptions.MissingSchema:
        req = get_req("https://{}".format(url))
    except requests.exceptions.RequestException as e:
        error(e)
        return None

    # Defaults to not found:
    program_id = None
    
    soup = BeautifulSoup(req.text, "lxml")
    
    if MIMIR_BASE_URL in url:
        json_info = json.loads(soup.script.get_text())
        # Check that it's a hit:
        if "activeMedia" in json_info:
            program_id = json_info["activeMedia"]["psId"]
        
    else:
        # New program ID style:
        program_id_meta = soup.find("meta", attrs={"name" : "programid"})
        if program_id_meta:
            program_id = program_id_meta["content"].strip()

        # Old program ID style:
        elif soup.figure and "data-video-id" in soup.figure:
            program_id = soup.figure['data-video-id']
        
    return program_id


def get_program_id(string):
    # Extract program ID from string. Either clean or inside url:
    # New program ID style:
    program_id_match = re.search("(^|/)([A-Z]{4}[0-9]{8})($|/)", string)
    # Old program ID style:
    if not program_id_match:
        program_id_match = re.search("(^|/)PS\*([0-9]+)($|/)", string)
    # nrk.no/skole style mediaId:
    if not program_id_match:
        media_id_match = re.search("(^|mediaId=)([0-9]+)($|&)", string)
        
    if program_id_match:
        program_id = program_id_match.group(2)
    elif media_id_match:
        program_id = get_program_id_online(MIMIR_BASE_URL.format(media_id_match.group(2)))
    # If not able to extract, try using string as url, search for program id in html:
    else:
        program_id = get_program_id_online(string)   # Returns None if not found

    return program_id
    
    
def main(programs):
    print("NRK Download {}\n".format(VERSION))
    for i, program in enumerate(programs):
        print("Downloading {} of {}:".format(i+1, len(programs)))
        program_id = get_program_id(program)
        if program_id:
            download(program_id)
        else:
            error("Could not parse program ID from '{}'".format(url))
        

def get_argument_parser():
    parser = argparse.ArgumentParser(description='Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).')
    parser.add_argument("PROGRAMS", type=str, nargs="+", help="A list of URLs or program IDs to download")
    return parser


if __name__ == "__main__":
    programs = get_argument_parser().parse_args().PROGRAMS
    main(programs)
