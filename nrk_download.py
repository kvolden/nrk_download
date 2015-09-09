#!/usr/bin/env python

import re
import os
import io
import sys
import requests
import datetime
import argparse
from bs4 import BeautifulSoup
from libs import hls

VERSION = "1.0.0"


def progress(pct):
    sys.stdout.write("\rProgress: {}%".format(pct))
    sys.stdout.flush()


def error(message):
    print("Error: {}".format(message))

    
def xml2srt(text=''):
    soup = BeautifulSoup(text)
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


def download(url):
    try:
        req = requests.get(url)
    except requests.exceptions.MissingSchema:
        req = get_req("http://{}".format(url))
    except requests.exceptions.RequestException as e:
        error(e)
        return

    soup = BeautifulSoup(req.text)

    # Critical elements:
    title_meta = soup.find("meta", attrs={"name" : "title"})
    player_div = soup.find(id="playerelement")
    if not title_meta or not player_div:
        error("Did not recognize HTML structure. Check your url.")
        return

    # Create filename from title:
    title = title_meta["content"].strip()
    out_filename = re.sub('[/\\\?%\*:|"<>]', '_', title)   # not allowed: / \ ? % * : | " < >

    # Add episode number to filename if it exists:
    episode_number_meta = soup.find("meta", attrs={"name" : "episodenumber"})
    if episode_number_meta:
        episode_number = int(episode_number_meta["content"].strip())
        out_filename += " E{:02d}".format(episode_number)

    # Print confirmation
    print(u"Found: {}".format(title))

    # Get url to videostream:
    video_url = player_div.get("data-hls-media")
    if not video_url:
        error("Could not find video stream.")
        return
    video_url = video_url.split("?")[0]

    # Ensure unique filename:
    if os.path.isfile(out_filename + ".ts"):
        index = 1
        while(os.path.isfile(out_filename + " ({}).ts".format(index))):
            index += 1
        out_filename = out_filename + " ({})".format(index)

    # Save subtitles if any:
    if player_div.get('data-subtitlesurl'):
        print(u"Saving {}.srt".format(out_filename))
        sub_url = "http://{}{}".format(req.url.split("/")[2], player_div.get("data-subtitlesurl"))

        sub_xml = requests.get(sub_url).text
        sub_srt = xml2srt(sub_xml)
    
        srtfile = io.open(out_filename + ".srt", "w")
        srtfile.write(sub_srt)
        srtfile.close()

    # Start dumping HLS stream
    print(u"Saving {}.ts\n".format(out_filename))
    hls.dump(video_url, out_filename + ".ts", progress)
    
    print("\n")

    
def main(urls):
    print("NRK Download {}\n".format(VERSION))
    for i, url in enumerate(urls):
        print("Downloading {}/{}:".format(i+1, len(urls)))
        download(url)


def getArgumentParser():
    parser = argparse.ArgumentParser(description='Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).')
    parser.add_argument("URL", type=str, nargs="+", help="A list of URLs to download")
    return parser

if __name__ == "__main__":
    urls = getArgumentParser().parse_args().URL
    main(urls)
