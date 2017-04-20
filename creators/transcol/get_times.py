#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Script to download time tables as PDF and calculate route durations based on relations for the routes in OpenStreetMap
from common import *
from feriados import *

import os
import sys
import io
import logging
import requests
import json
import datetime
import time
from unidecode import unidecode
routingE = "YOURS"
try:
    import osrm
    routingE = "OSRM"
except:
    pass
import overpass


logger = logging.getLogger("GTFS_get_times")
logging.basicConfig(filename="./GTFS_get_times.log", level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s - %(message)s", datefmt="%Y/%m/%d %H:%M:%S:")

# PDFs are stored here
baseurl = "https://ceturb.es.gov.br/"

debugMe = True

# List of route numbers

config = {}
with open('transcol.json', 'r') as infile:
    config = json.load(infile)

durationsList = {}
try:
    with open('durations.json', 'r') as infile:
        durationsList = json.load(infile)
except:
    pass
myRoutes = {}
myRoutes[u"updated"] = str(datetime.date.today())
myRoutes[u"operator"] = u"Transcol"
myRoutes[u"network"] = u"Transcol"
myRoutes[u"source"] = baseurl
myRoutes["routes"] = {}

def calculate_end_time(start_time, duration):
    if duration < 1:
        duration = 60
    end_time = start_time
    day = 0
    hr = int(start_time[:2])
    min = int(start_time[3:])
    min += duration
    while min > 59:
        hr += 1
        min -= 60
    while hr > 23:
        hr -= 24 # Should we put a day+1 variable as well?
        day += 1
    end_time = "{0}:{1}".format(str(hr).zfill(2), str(min).zfill(2))
    if day > 0:
        end_time = "{0}+{1}".format(end_time, str(day))
    return end_time

def debug_to_screen(text, newLine=True):
    if debugMe:
        if newLine:
            print text
        else:
            print text,

def getLines():
    downloadURL = "https://sistemas.es.gov.br/webservices/ceturb/onibus/api/ConsultaLinha/"
    routes = []
    myJSON = None
    r = False
    while r == False:
        try:
            r = requests.get(downloadURL, timeout=30)
        except requests.exceptions.ReadTimeout as e:
            r = False
        except requests.exceptions.ConnectionError as e:
            r = False
#    print r.content
        try:
            myJSON = json.dumps(json.loads(r.content))
        except:
            #            print "r is not JSON"
            r = False
    for i in json.loads(myJSON):
        #        print i
        #        print i["Linha"], i["Descricao"]
        routes.append( [ str(int(i[u"Linha"])), lower_capitalized(unicode(i[u"Descricao"])) ] )
    return routes

def getTimes(ref):
    downloadURL = "https://sistemas.es.gov.br/webservices/ceturb/onibus/api/BuscaHorarios/" + ref
    myJSON = None
    myReturn = {}
    myReturn["Stations"] = {}
    myReturn[ref] = {}
    myReturn[ref]["Mo-Fr"] = {}
    myReturn[ref]["Sa"] = {}
    myReturn[ref]["Su"] = {}
    myReturn[ref]["Ex"] = {}
    for rr in myReturn[ref]:
        myReturn[ref][rr]["Ida"] = []
        myReturn[ref][rr]["Volta"] = []
#        myReturn[ref][rr]["Circular"] = []
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
            #            print "r is not JSON"
            r = False
    for i in json.loads(myJSON):
        nuRef = None
        if len(i["Tipo_Orientacao"]):
            nuRef = ref + i["Tipo_Orientacao"]
            nuRef = nuRef.strip()
            try:
                test = myReturn[nuRef]
            except:
                myReturn[nuRef] = {}
                myReturn[nuRef]["Mo-Fr"] = {}
                myReturn[nuRef]["Sa"] = {}
                myReturn[nuRef]["Su"] = {}
                myReturn[nuRef]["Ex"] = {}
                for rr in myReturn[nuRef]:
                    myReturn[nuRef][rr]["Ida"] = []
                    myReturn[nuRef][rr]["Volta"] = []
#                    myReturn[nuRef][rr]["Circular"] = []
        else:
            nuRef = ref
        day = None
        if i["TP_Horario"] == 1:
            day = "Mo-Fr"
        elif i["TP_Horario"] == 2:
            day = "Sa"
        elif i["TP_Horario"] == 3:
            day = "Su"
        elif i["TP_Horario"] == 4:
            day = "Ex"
        else:
            print i["Descricao_Hora"]
        direction = None
        if i["Terminal_Seq"] == 1:
            direction = "Ida"
        elif i["Terminal_Seq"] == 2:
            direction = "Volta"
#        else:
#            print i["Descricao_Hora"], i["Tipo_Orientacao"], i["Hora_Saida"], i["TP_Horario"], i["Terminal_Seq"], i["Dt_Inicio"], lower_capitalized(i["Desc_Terminal"]), str(int(i["Linha"]))
#        print nuRef, i["Hora_Saida"], "-",
        myReturn[nuRef][day][direction].append(i["Hora_Saida"])
        myReturn["Stations"][direction] = lower_capitalized(i["Desc_Terminal"])
#    print myReturn
    return myReturn

def getObservations(ref):
    downloadURL = "https://sistemas.es.gov.br/webservices/ceturb/onibus/api/BuscaHorarioObse/" + ref
    myJSON = None
    myObs = []
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
            #            print "r is not JSON"
            r = False
    for i in json.loads(myJSON):
        #        print i["Tipo_Orientacao"], "-", i["Descricao_Orientacao"]
        myObs.append( [ i["Tipo_Orientacao"], i["Descricao_Orientacao"] ] )
    return myObs

def create_json(ref, fromV, toV, d, times, duration=60):
    #    print ref, "-", fromV, "->", toV, "(", d, ")", len(times), "-", duration
    times.sort()
    retValue = {}
    retValue[u"from"] = fromV
    retValue[u"to"] = toV
    if d == "Su":
        retValue[u"service"] = [ d ]
        for i in get_saturday_holidays():
            retValue[u"service"].append(i)
        for i in get_weekday_holidays():
            retValue[u"service"].append(i)
        retValue[u"exceptions"] = []
    elif d == "Sa":
        retValue[u"service"] = [ d ]
        retValue[u"exceptions"] = [ get_saturday_holidays() ]
    elif d == "Ex":
        retValue[u"service"] = [ get_atypical_days() ]
        retValue[u"exceptions"] = []
    else:
        retValue[u"service"] = [ d ]
        retValue[u"exceptions"] = [ get_weekday_holidays() ]
    retValue[u"stations"] = [ fromV, toV ]
    retValue[u"times"] = []
    for t in times:
        tmp = calculate_end_time(t, duration)
        retValue[u"times"].append( [ t, tmp ] )
    if len(retValue["times"]) > 0:
        try:
            test = myRoutes["routes"][ref]
        except:
            myRoutes["routes"][ref] = []
        myRoutes["routes"][ref].append(retValue)

for i in getLines():
    myRefs = []
    myTimes = {}
    ref = str(i[0])
    myRefs.append(ref)
    name = i[1]
    print ref, name
    logger.info("Gathering times for route %s: %s", ref, name)
    myTimes = getTimes(ref)
    myObs = getObservations(ref)
    for j in myObs:
        tmp = ref + j[0]
        myRefs.append(tmp)
    try:
        test = myTimes["Stations"]["Volta"]
    except:
        myTimes["Stations"]["Volta"] = myTimes["Stations"]["Ida"]
    for ref in myRefs:
        try:
            durations = durationsList[ref]
        except:
            durations = [ -10, -10 ]
        myDays = [ u"Mo-Fr", u"Sa", u"Su", u"Ex" ]
        for d in myDays:
            create_json(ref, myTimes["Stations"]["Ida"], myTimes["Stations"]["Volta"], d, myTimes[ref][d]["Ida"], durations[0])
            create_json(ref, myTimes["Stations"]["Volta"], myTimes["Stations"]["Ida"], d, myTimes[ref][d]["Volta"], durations[1])
    if len(myObs) > 0:
        try:
            obs = myRoutes["routes"][ref]["observations"]
        except:
            myRoutes["routes"][ref] = {}
            myRoutes["routes"][ref]["observations"] = []
        for o in myObs:
            myRoutes["routes"][ref]["observations"].append(o)

with open('times.json', 'w') as outfile:
    json.dump(myRoutes, outfile, sort_keys=True, indent=4)






