nrk_download
============

Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).

Usage:

```python nrk_download.py PROGRAMS...```

PROGRAMS is one or more arguments consisting of either the programs' program ID or URLs of the pages of the programs. Found to work on http://tv.nrk.no, http://tv.nrksuper.no, http://radio.nrk.no and http://www.nrk.no/video/. Other sources may work, but you might have to find the program ID in the source yourself.

Subtitles will be downloaded if they are available, converted to SubRip format and saved as a separate .srt file. Video and audio will be saved as an MPEG Transport Stream container with original encodings.

####Tip:
Sequential programs like episodes in a season usually have program IDs with an incrementing number. This can sometimes be taken advantage of in order to download complete seasons. For example, bash users can download all July 2015 episodes of _Dagsrevyen_ using brace expansion like this:

```python ./nrk_download.py NNFA1907{01..31}15```

####Note:
The purpose of this program is NOT to facilitate copyright violations or pirating of content. The author of this program takes no responsibility for other people's irresponsible or illegal use of it.

Please report any issues at https://github.com/kvolden/nrk_download/issues