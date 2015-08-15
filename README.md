nrk_download
============

Python script for downloading video and audio from NRK (Norwegian Broadcasting Corporation).

Usage:

```python nrk_download.py URL...```

URL is one or more URLs of the pages of the programs, on either on http://tv.nrk.no, http://tv.nrksuper.no or http://radio.nrk.no.

Subtitles will be downloaded if they are available, converted to SubRip format and saved as a separate .srt file. Video and audio will be saved as an MPEG Transport Stream container with original encodings.

####Tip:
Everything in the URL following the program ID, can be removed. Thus "https://tv.nrk.no/serie/dagsrevyen/NNFA19070115/01-07-2015" can be reduced to "https://tv.nrk.no/serie/dagsrevyen/NNFA19070115". Furthermore, sequential programs like episodes in a season usually have program IDs with an incrementing number. This can sometimes be taken advantage of in order to download complete seasons. For example, bash users can download all July 2015 episodes of _Dagsrevyen_ using brace expansion like this:

```python ./nrk_download.py https://tv.nrk.no/serie/dagsrevyen/NNFA1907{01..31}15```
