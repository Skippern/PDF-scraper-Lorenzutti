#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Script to download time tables as PDF and calculate route durations based on relations for the routes in OpenStreetMap
from common import *

import os
import sys
import io
import logging
import requests
import json
#from unidecode import unidecode


logger = logging.getLogger("GTFS_get_durations")
logging.basicConfig(filename="/var/log/GTFS/seletivo.log", level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s - %(message)s", datefmt="%Y/%m/%d %H:%M:%S:")

# PDFs are stored here
baseurl = "http://ceturb.es.gov.br/"

stationList = {}

def getRefs(ref):
    ref = ref.strip()
    try:
        test = stationList[ref][0]
    except KeyError:
        stationList[ref] = [None, None]
    debug_to_screen(u"Testing getRefs on {0}".format(ref) )
    downloadURL = "https://sistemas.es.gov.br/webservices/ceturb/onibus/api/BuscaHorarios/" + ref
    myJSON = None
    retValue = [ unicode(ref) ]
    r = False
    while r == False:
        try:
            r = requests.get(downloadURL, timeout=30)
        except requests.exceptions.ReadTimeout as e:
            r = False
        except requests.exceptions.ConnectionError as e:
            r = False
        try:
            myJSON = json.dumps(json.loads(r.content))
        except:
            r = False
    for i in json.loads(myJSON):
        if i[u"Terminal_Seq"] == 1:
            try:
                stationList[ref][0] = lower_capitalized(i[u"Desc_Terminal"])
            except:
                stationList[ref][0] = u"Unknown"
        elif i[u"Terminal_Seq"] == 2:
            try:
                stationList[ref][1] = lower_capitalized(i[u"Desc_Terminal"])
            except:
                stationList[ref][1] = u"Unknown"
        else:
            debug_to_screen(u"{0} - {1}".format(i[u"Terminal_Seq"], i[u"Desc_Terminal"]))
        try:
            if len(i[u"Tipo_Orientacao"]) > 0 and i[u"Tipo_Orientacao"] != u" ":
                tmp = ref + i[u"Tipo_Orientacao"]
                tmp = tmp.strip()
                retValue.append(tmp)
        except:
            pass
    retValue = uniq(retValue)
    return retValue

config = {}
with open('seletivo.json', 'r') as infile:
    config = json.load(infile)

durationsList = {}
try:
    with open('durations.json', 'r') as infile:
        durationsList = json.load(infile)
except:
    pass
durationsList[u"updated"] = str(datetime.date.today())
durationsList[u"operator"] = u"Seletivo"
durationsList[u"network"] = u"Seletivo"
durationsList[u"source"] = baseurl

def getStations(ref):
    #    return stationList[ref]
    stations = [ None, None ]
    if ref == u"1902":
        stations[0] = lower_capitalized(u"Marcilio de Noronha")
    elif ref == u"1604":
        stations[0] = lower_capitalized(u"Itaparica")
    downloadURL = "https://sistemas.es.gov.br/webservices/ceturb/onibus/api/BuscaHorarios/" + ref
    myJSON = None
    r = False
    while r == False:
        try:
            r = requests.get(downloadURL, timeout=30)
        except:
            r = False
        try:
            myJSON = json.dumps(json.loads(r.content))
        except:
            r = False
    for i in json.loads(myJSON):
        if i[u"Terminal_Seq"] == 1:
            stations[0] = lower_capitalized(i[u"Desc_Terminal"])
        elif i[u"Terminal_Seq"] == 2:
            stations[1] = lower_capitalized(i[u"Desc_Terminal"])
        else:
            debug_to_screen( "{0} - {1}".format(i[u"Terminal_Seq"], i[u"Desc_Terminal"]))
    return stations

for i in getLines():
    name = i[1]
    ref = i[0]
    origin, destination = getStations(ref)
    print ref, name
    print u"    From", origin
    print u"    To", destination
    for myRef in getRefs(ref):
        durationsList[myRef] = [ get_duration(myRef, origin, destination, config[u"query"][u"bbox"]), get_duration(myRef, destination, origin, config[u"query"][u"bbox"]) ]
        print u"Durations calculated {0}: {1} / {2}".format( myRef, durationsList[myRef][0], durationsList[myRef][1] )

with open('durations.json', 'w') as outfile:
    json.dump(durationsList, outfile, sort_keys=True, indent=4)






