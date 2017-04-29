#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Script to download time tables as PDF and calculate route durations based on relations for the routes in OpenStreetMap
from commons import *

import os
import sys
import io
import logging
import requests
import json
import datetime
import time
from unidecode import unidecode
try:
    import osrm
except:
    pass
import overpass


logger = logging.getLogger("GTFS_router")

def route_osrm_py(points):
    duration = 0
    result = osrm.match(points, steps=False, overview="full")
    tmp = result["total_time"]
    duration = int(float(tmp)/60.0)
    return duration

def route_orsm_web(points):
    duration = 0.0
    routingProfile = "car"
    routingBase = "http://router.project-osrm.org/route/v1/"+routingProfile+"/"
    waypoints = ""
    routingOptions = ""
    routeJSON = None
    for p in points:
        if len(waypoints) == 0:
            waypoints = "{0},{1}".format(str(p[1]),str(p[0]))
        else:
            waypoints = "{0};{1},{2}".format(waypoints,str(p[1]),str(p[0]))
        r = False
    while r == False:
        fullRoutingString = routingBase+waypoints+routingOptions
        logger.debug(fullRoutingString)
        try:
            r = requests.get(fullRoutingString, timeout=60)
        except:
            r = False
        try:
            routeJSON = json.loads(r.content)
        except:
            r = False
    for dr in routeJSON["routes"]:
        duration += dr["duration"]
    debug_to_screen( "Duration: {0} seconds / {1} minutes".format(int(duration), int(duration / 60)) )
    duration = (duration / 60)
    return int(duration)

def route_yours_web(points):
    duration = 0
    routingBase = "http://www.yournavigation.org/api/1.0/gosmore.php?format=json&v=psv&fast=1"
    fromP = None
    for p in points:
        toP = p
        if fromP == None:
            fromP = toP
        else:
            r = False
            while r == False:
                fullRoutingString = "{0}&flat={1}&flon={2}&tlat={3}&tlon={4}".format(routingBase,fromP[0],fromP[1],toP[0],toP[1])
                logger.debug(fullRoutingString)
                try:
                    r = requests.get(fullRoutingString, timeout=30)
                except ValueError:
                    r = False
                except requests.exceptions.ReadTimeout:
                    r = False
                except requests.exceptions.ConnectionError:
                    r = False
                try:
                    if len(r.content) < 50:
                        print r.content
                    getDuration = r.content
                    duration += int(getDuration[(getDuration.find("<traveltime>")+12):getDuration.find("</traveltime>")])
                except ValueError:
                    r = False
                except AttributeError:
                    r = False
        fromP = toP
    duration = int( float(duration) / 60.0 ) + int( float(len(points) * 10) / 60.0 )
    return duration

def get_duration(ref, origin, destination, bbox):
    duration = 0
    points = []
    # Overpass get relation
    searchString = u"relation[\"type\"=\"route\"][\"route\"=\"bus\"][\"ref\"=\"{0}\"][\"from\"~\"{1}\"][\"to\"~\"{2}\"]({3},{4},{5},{6});out body;>;".format(unicode(ref), unicode(origin), unicode(destination), bbox["s"], bbox["w"], bbox["n"], bbox["e"]).encode('ascii', 'replace').replace(u"?", u".")
    result = overpasser(searchString)
    nodeList = []
    # Make points list
    if len(result["elements"]) < 1:
        logger.error("No relation found: \"%s\" from %s to %s", unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination)))
        debug_to_screen( "    Investigate route \"{0}\" from {1} to {2}. Relation not found".format(unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination))) )
        duration = -5
        return duration
    for elm in result["elements"]:
        if elm["type"] == u"relation":
            if elm["members"][0]["role"] != u"stop":
                logger.error("Route \"%s\" from %s to %s doesn't begin with a stop", unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination)))
                debug_to_screen( "    Investigate route \"{0}\" from {1} to {2}. Route doesn't begin with a stop".format(unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination))) )
                return -3
            if elm["members"][-1]["role"] != u"stop":
                logger.error("Route \"%s\" from %s to %s doesn't end with a stop", unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination)))
                debug_to_screen( "    Investigate route \"{0}\" from {1} to {2}. Route doesn't end with a stop".format(unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination))) )
                return -4
            for m in elm["members"]:
                if m["role"] == u"stop" and m["type"] == u"node":
                    nodeList.append(m["ref"])
    for testNode in nodeList:
        for elm in result["elements"]:
            if elm["type"] == u"node" and elm["id"] == testNode:
                points.append( ( elm["lat"], elm["lon"] ) )
    if len(points) == 0:
        logger.error("Relation have no defined stops: \"%s\" from %s to %s", unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination)))
        debug_to_screen( "    Investigate route \"{0}\" from {1} to {2}. Relation have no stops mapped".format(unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination))) )
        duration = -1
        return duration
    elif len(points) == 1:
        logger.error("Relation have only one defined stop: \"%s\" from %s to %s", unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination)))
        debug_to_screen( "    Investigate route \"{0}\" from {1} to {2}. Relation have only one defined stop".format(unidecode(unicode(ref)), unidecode(unicode(origin)), unidecode(unicode(destination))) )
        duration = -2
        return duration
    # Get Route
    try:
        duration = route_osrm_py(points)
    except:
        logger.warning("Routing with OSRM Python wrapper failed")
    if duration < 1:
        try:
            duration = route_orsm_web(points)
        except:
            logger.warning("Routing with OSRM Web API failed")
    if duration < 1:
        try:
            duration = route_yours_web(points)
        except:
            logger.warning("Routing with YOUR Web API failed")
    # Return
    logger.info("Route \"%s\" from %s to %s calculated with duration %s minutes", ref, origin, destination, (duration + 1) )
#    duration = duration + 1
    return (duration + 1)

