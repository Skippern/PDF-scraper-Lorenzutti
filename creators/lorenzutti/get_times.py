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
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure, LTImage, LTRect
from pdfminer.converter import PDFPageAggregator

logger = logging.getLogger("GTFS_get_times")
logging.basicConfig(filename="/var/log/GTFS/lorenzutti.log", level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s - %(message)s", datefmt="%Y/%m/%d %H:%M:%S:")

cal = Guarapari()

# PDFs are stored here
baseurl = "http://www.expressolorenzutti.com.br/horarios"

blacklisted = [ ]
whitelisted = [ ]


ignoreVariants = True
blacklistVariants = True

myRoutes = {}

durationsList = {}
with open('durations.json', 'r') as infile:
    durationsList = json.load(infile)

myRoutes[u"updated"] = str(datetime.date.today())
myRoutes[u"operator"] = u"Expresso Lorenzutti"
myRoutes[u"network"] = u"PMG"
myRoutes[u"source"] = baseurl
myRoutes[u"excluded_lines"] = []
myRoutes[u"routes"] = {}

whitelistSet = set()

for wl in whitelisted:
    whitelistSet.add(wl)

for bl in blacklisted:
    myRoutes[u"excluded_lines"].append(bl)

for i in getLines():
    pdf = download_pdf(i)
    if pdf == None:
        continue

    # Start pdfminer
    parser = PDFParser(io.BytesIO(pdf))
    document = PDFDocument(parser)
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for page in PDFPage.create_pages(document):
        interpreter.process_page(page)
        layout = device.get_result()
        fieldNr = 0
        ref = u""
        name = u""
        origin = u""
        destination = u""
        wd_ida = []
        wd_volta = []
        sa_ida = []
        sa_volta = []
        su_ida = []
        su_volta = []
        for object in layout:
            if not issubclass(type(object), LTRect):
                # Here we have all data objects on the page, we now need to get their values and match them with the right variables
                tmp = object.get_text().strip()
                if tmp == u"EXPRESSO LORENZUTTI" or tmp == u"ITINERARIO" or tmp == u"AOS DOMINGOS" or tmp == u"AOS SABADOS" or tmp == u"DIAS UTEIS":
                    continue
                if tmp == u"PARTIDAS:":
                    fieldNr += 1
                    continue
                tmpList = tmp.split(u" ")
                if tmpList[0] == u"Início" or tmpList[0] == u"Inicio":
                    continue
                if fieldNr == 0:
                    tmp = object.get_text()
                    tmpList = tmp.split(u" ")
                    tmpList.pop(0)
                    ref = tmpList[0]
                    tmpList.pop(0)
                    tmpList.pop(0)
                    name = lower_capitalized(u" ".join(tmpList).strip())
                    fieldNr += 1
                elif fieldNr == 2:
                    origin = lower_capitalized(object.get_text().strip())
                    fieldNr += 1
                elif fieldNr == 4:
                    destination = lower_capitalized(object.get_text().strip())
                    fieldNr += 1
                else:
                    tmp = object.get_text()
                    # Try to split tmp at linebreaks for fields with multiple times
                    tmpList = tmp.split(u"\n")
                    for t in tmpList:
                        t = t.strip()
                        for x in t.split():
                            if x[0] == u"0" or x[0] == u"1" or x[0] == u"2":
                                if len(t) > 10:
                                    continue
                                dir = u"ida"
                                if object.bbox[0] > 225.0:
                                    dir = u"volta"
                                dayOfWeek = u"sa"
                                if object.bbox[1] < 236.0:
                                    dayOfWeek = u"su"
                                elif object.bbox[1] > 415.0:
                                    dayOfWeek = u"wd"
                                if dir == u"ida" and dayOfWeek == u"wd":
                                    wd_ida.append(t)
                                elif dir == u"volta" and dayOfWeek == u"wd":
                                    wd_volta.append(t)
                                elif dir == u"ida" and dayOfWeek == u"sa":
                                    sa_ida.append(t)
                                elif dir == u"volta" and dayOfWeek == u"sa":
                                    sa_volta.append(t)
                                elif dir == u"ida" and dayOfWeek == u"su":
                                    su_ida.append(t)
                                elif dir == u"volta" and dayOfWeek == u"su":
                                    su_volta.append(t)
                            else:
                                continue
        name = name.split(u"\n")[0]
        print ref, name
        print u"    From", origin
        print u"    To", destination
        # Here we need some code to handle variations, for now we'll just strip the information after the time stamp
        wd_ida = uniq(wd_ida)
        wd_volta = uniq(wd_volta)
        sa_ida = uniq(sa_ida)
        sa_volta = uniq(sa_volta)
        su_ida = uniq(su_ida)
        su_volta = uniq(su_volta)
        wd_ida.sort()
        wd_volta.sort()
        sa_ida.sort()
        sa_volta.sort()
        su_ida.sort()
        su_volta.sort()
        myVariations = []
        myVariationList = {}
        variationSet = set()
        myVariationList[ref] = {}
        myVariationList[ref][u"ida"] = {}
        myVariationList[ref][u"volta"] = {}
        myVariationList[ref][u"ida"][u"Mo-Fr"] = []
        myVariationList[ref][u"volta"][u"Mo-Fr"] = []
        myVariationList[ref][u"ida"][u"Sa"] = []
        myVariationList[ref][u"volta"][u"Sa"] = []
        myVariationList[ref][u"ida"][u"Su"] = []
        myVariationList[ref][u"volta"][u"Su"] = []
        while len(wd_ida) > 0:
            t = wd_ida[0]
            wd_ida.pop(0)
            debug_to_screen(u"(wi) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(wi) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"ida"][u"Mo-Fr"].append(newT)
                    else:
                        debug_to_screen(u"Forced variation (wi)")
                myVariations.append(variation)
                tmp = u"{0} {1}".format(ref, variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"ida"][u"Mo-Fr"].append(newT)
            else:
                debug_to_screen(len(t))
                myVariationList[ref][u"ida"][u"Mo-Fr"].append(t)
        while len(wd_volta) > 0:
            t = wd_volta[0]
            wd_volta.pop(0)
            debug_to_screen(u"(wv) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(wv) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"volta"][u"Mo-Fr"].append(newT)
                    else:
                        debug_to_screen(u"Forced variation (wv)")
                myVariations.append(variation)
                tmp = u"{0} {1}".format(ref, variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"volta"][u"Mo-Fr"].append(newT)
            else:
                myVariationList[ref][u"volta"][u"Mo-Fr"].append(t)
                debug_to_screen(len(t))
        while len(sa_ida) > 0:
            t = sa_ida[0]
            sa_ida.pop(0)
            debug_to_screen(u"(si) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(si) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"ida"][u"Sa"].append(newT)
                tmp = u"{0} {1}".format(ref, variation)
                myVariations.append(variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"ida"][u"Sa"].append(newT)
            else:
                myVariationList[ref][u"ida"][u"Sa"].append(t)
                debug_to_screen(len(t))
        while len(sa_volta) > 0:
            t = sa_volta[0]
            sa_volta.pop(0)
            debug_to_screen(u"(sv) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(sv) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"volta"][u"Sa"].append(newT)
                tmp = u"{0} {1}".format(ref, variation)
                myVariations.append(variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"volta"][u"Sa"].append(newT)
            else:
                myVariationList[ref][u"volta"][u"Sa"].append(t)
                debug_to_screen(len(t))
        while len(su_ida) > 0:
            t = su_ida[0]
            su_ida.pop(0)
            debug_to_screen(u"(di) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(di) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"ida"][u"Su"].append(newT)
                myVariations.append(variation)
                tmp = u"{0} {1}".format(ref, variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"ida"][u"Su"].append(newT)
            else:
                debug_to_screen(len(t))
                myVariationList[ref][u"ida"][u"Su"].append(t)
        while len(su_volta) > 0:
            t = su_volta[0]
            su_volta.pop(0)
            debug_to_screen(u"(dv) {0}".format(t), False)
            if len(t) > 5:
                newT = t[:5]
                variation = t[5:].strip()
                debug_to_screen(u"(dv) Variation in \"{0}\"/\"{1}\"/\"{2}\"".format(t,newT,variation))
                if ignoreVariants:
                    if ref not in whitelistSet:
                        myVariationList[ref][u"volta"][u"Su"].append(newT)
                tmp = u"{0} {1}".format(ref, variation)
                myVariations.append(variation)
                if variation not in variationSet:
                    variationSet.add(variation)
                    myVariationList[tmp] = {}
                    myVariationList[tmp][u"ida"] = {}
                    myVariationList[tmp][u"volta"] = {}
                    myVariationList[tmp][u"ida"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"volta"][u"Mo-Fr"] = []
                    myVariationList[tmp][u"ida"][u"Sa"] = []
                    myVariationList[tmp][u"volta"][u"Sa"] = []
                    myVariationList[tmp][u"ida"][u"Su"] = []
                    myVariationList[tmp][u"volta"][u"Su"] = []
                myVariationList[tmp][u"volta"][u"Su"].append(newT)
            else:
                debug_to_screen(len(t))
                myVariationList[ref][u"volta"][u"Su"].append(t)
        durationIda = 0
        durationVolta = 0
        if len(myVariations) > 0:
            myVariations = uniq(myVariations)
            logger.warning(u"Variations detected in %s: %s", ref, ", ".join(myVariations))
            debug_to_screen(u"Known variations: ",False)
            for i in myVariations:
                debug_to_screen( u"{0}, ".format(i),False)
                tmp = u"{0} {1}".format(ref, i)
                try:
                    if blacklistVariants and durationsList[tmp][0] < 0 and durationsList[tmp][1] < 0:
                        myRoutes[u"excluded_lines"].append(tmp)
                        logger.info(u"Route \"%s\" added to blacklist", tmp)
                except:
                    pass
                try:
                    if durationsList[tmp][0] > 0:
                        durationIda = durationsList[ref][0]
                except:
                    durationIda = -9
                try:
                    if durationsList[tmp][1] > 0:
                        durationVolta = durationsList[ref][1]
                except:
                    durationVolta = -9
                myRoutes[u"routes"][tmp] = []
                myDays = [ u"Mo-Fr", u"Sa", u"Su" ]
                for d in myDays:
                    myRoutes = create_json(myRoutes, cal, tmp, origin, destination, d, myVariationList[tmp][u"ida"][d], durationIda)
                    myRoutes = create_json(myRoutes, cal, tmp, destination, origin, d, myVariationList[tmp][u"volta"][d], durationVolta)
            debug_to_screen(u"")
        durationIda = 0
        durationVolta = 0
        try:
            if durationsList[ref][0] > 0:
                durationIda = durationsList[ref][0]
        except:
            durationIda = -9
        try:
            if durationsList[ref][1] > 0:
                durationVolta = durationsList[ref][1]
        except:
            durationVolta = -9
        myRoutes[u"routes"][ref] = []
        myDays = [ u"Mo-Fr", u"Sa", u"Su" ]
        for d in myDays:
            myRoutes = create_json(myRoutes, cal, ref, origin, destination, d, myVariationList[ref][u"ida"][d], durationIda)
            myRoutes = create_json(myRoutes, cal, ref, destination, origin, d, myVariationList[ref][u"volta"][d], durationVolta)

newBlacklist = uniq(myRoutes[u"excluded_lines"])
newBlacklist.sort()

for wl in whitelisted:
    try:
        newBlacklist.remove(wl)
        logger.warning(u"%s removed from blacklist", wl)
    except:
        logger.error(u"Something went wrong: %s is not blacklisted", wl)
        pass

myRoutes[u"excluded_lines"] = newBlacklist
logger.info(u"Complete blacklist: %s", ", ".join(newBlacklist))

with open('times.json', 'w') as outfile:
    json.dump(myRoutes, outfile, sort_keys=True, indent=4)






