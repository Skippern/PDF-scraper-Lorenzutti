#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Script to download time tables as PDF and extract times into containers that can be used by OSM2GFTS
#  or similar
from common import *

import os
import sys
import io
import logging
import requests
import json
import datetime

logger = logging.getLogger("GTFS_get_times")
logging.basicConfig(filename="/var/log/GTFS/alvorada.log", level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s - %(message)s", datefmt="%Y/%m/%d %H:%M:%S:")

cal = EspiritoSanto()
noneCal = CalendarNull()

blacklisted = [ ]

myRoutes = {}

durationsList = {}
with open('durations.json', 'r') as infile:
    durationsList = json.load(infile)

source = {}
with open('../../sources/der-es/alvorada.json') as infile:
    source = json.load(infile)

myRoutes[u"updated"] = str(datetime.date.today())
myRoutes[u"operator"] = u"Viação Alvorada"
myRoutes[u"network"] = u"Alvorada"
myRoutes[u"source"] = u"DER-ES"
myRoutes[u"excluded_lines"] = []
myRoutes[u"routes"] = {}

for bl in blacklisted:
    myRoutes[u"excluded_lines"].append(bl)

for ref, origin, destination, via, duration in durationsList['routes']:
    if duration > 0:
        for s in source['routes'][ref]:
            if s['from'] == origin and s['to'] == destination:
                myRoutes = create_json(myRoutes, noneCal, ref, origin, destination, s['services'], s['times'], duration)
            else:
                myRoutes['excluded_lines'].append(ref)

        

newBlacklist = uniq(myRoutes[u"excluded_lines"])
newBlacklist.sort()

myRoutes[u"excluded_lines"] = newBlacklist
logger.info(u"Complete blacklist: %s", ", ".join(newBlacklist))

with open('times.json', 'w') as outfile:
    json.dump(myRoutes, outfile, sort_keys=True, indent=4)






