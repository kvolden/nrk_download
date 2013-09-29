nrk_download
============

Python script for downloading videos from NRK (Norwegian Broadcasting Corporation) using ffmpeg/avconv.

Usage:

python ./nrk_download.py -u {url} [-a {audiocodec}]

{url} is the url of the page of the program, on either on tv.nrk.no or tv.nrksuper.no.

{audiocodec} is the name of the audiocodec as it is defined in ffmpeg/avconv, passed with the -a argument if the audio is to be transcoded.

Subtitles will be downloaded if they are available, converted to SubRip format and included in the resulting mkv-container as a subtitles stream.
