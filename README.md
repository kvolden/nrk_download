nrk_download
============

Python script for downloading videos from NRK (Norwegian Broadcasting Corporation).

Usage:

python ./nrk_download.py -u {url}

{url} is the url of the page of the program, on either on tv.nrk.no or tv.nrksuper.no.

Subtitles will be downloaded if they are available, converted to SubRip format and saved as a separate .srt file. Video will be saved as an MPEG Transport Stream container with original encodings.
