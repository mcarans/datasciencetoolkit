#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Combine GeoJSON locations into a single code and name consisting of the admin 1-N names ie.
admin name 1|admin name 2|admin name N but with logic that if admin name N is unique then the preceding
admin names are not needed"""
import getopt
import json
import logging.config

import sys

from utilities.loader import script_dir_plus_file, load_yaml

logger = logging.getLogger(__name__)


class GeoJSONLocations:
    def __init__(self, config: dict):
        self.aggregateatadminlevel = config['aggregateatadminlevel']
        self.ignore0locationcode = config.get('ignore0locationcode', False)
        self.addlocationcode = config['addlocationcode']
        self.shrinklocationamesifpos = config['shrinklocationamesifpos']
        self.dontaddlocationamesifpos = config['dontaddlocationamesifpos']
        self.ignoreleadingcharacters = config.get('ignoreleadingcharacters', 0)
        self.geojson_admcode = config['geojson_admcode']
        self.geojson_admname = config['geojson_admname']
        self.geojson_outputfile = config['geojson_locations_file']

        with open(config['geojson_inputfile'], 'rt') as f:
            self.jsondict = json.loads(f.read())

        self.admlowestnametolocationcodename = dict()
        self.locationcodetoname = dict()
        self.locationcodetofullname = dict()
        self.locationnametocode = dict()
        self.locationnameadm1admlowesttocode = dict()
        self.locationnameadm1admswitchtocode = dict()

    @staticmethod
    def removezeros(strval):
        try:
            return '%d' % int(strval)
        except ValueError:
            return strval

    def combine_location(self):
        lowestadminnamesunique = True
        for area in self.jsondict['features']:
            properties = area['properties']
            admcode = []
            admname = []
            for i in range(0, self.aggregateatadminlevel):
                admcodepart = str(properties[self.geojson_admcode[i]])
                admcode.append(self.removezeros(admcodepart[self.ignoreleadingcharacters:]))
                admname.append(properties[self.geojson_admname[i]])

            locationcode = admcode[0]
            if self.ignore0locationcode and locationcode == '0':
                continue
            locationname = admname[0]
            for i in range(1, self.aggregateatadminlevel):
                locationcode = '%s|%s' % (locationcode, admcode[i])
                locationname = '%s|%s' % (locationname, admname[i])
            self.locationcodetofullname[locationcode] = locationname
            self.locationnametocode[locationname.lower().replace('-', ' ')] = locationcode

            admlowestname = admname[self.aggregateatadminlevel - 1]
            # Check if the lowest level admin name has been found before with a different location code - if so we must use
            # the full name: admin 1|...admin N. If not, the lowest level admin name is unique and we can use it.
            if self.shrinklocationamesifpos:
                clashingadmlowest = self.admlowestnametolocationcodename.get(admlowestname.lower().replace('-', ' '))
                if clashingadmlowest and locationcode != clashingadmlowest[0]:
                    self.locationcodetoname[clashingadmlowest[0]] = clashingadmlowest[1]
                    self.locationcodetoname[locationcode] = locationname
                    lowestadminnamesunique = False
                else:
                    self.locationcodetoname[locationcode] = admlowestname
            else:
                self.locationcodetoname[locationcode] = locationname
            self.admlowestnametolocationcodename[admlowestname.lower().replace('-', ' ')] = (locationcode, locationname)
            locationadm1admlowestname = '%s|%s' % (admname[0], admlowestname)
            self.locationnameadm1admlowesttocode[locationadm1admlowestname.lower().replace('-', ' ')] = locationcode
            admno = len(self.geojson_admname)
            if admno > self.aggregateatadminlevel:
                admswitch = properties[self.geojson_admname[admno - 1]]
                locationadm1admswitchname = '%s|%s' % (admname[0], admswitch)
                self.locationnameadm1admswitchtocode[locationadm1admswitchname.lower().replace('-', ' ')] = locationcode
        return lowestadminnamesunique

    def output_geojson(self, lowestadminnamesunique):
        for area in self.jsondict['features']:
            properties = area['properties']
            admcode = []
            for i in range(0, self.aggregateatadminlevel):
                admcodepart = str(properties[self.geojson_admcode[i]])
                admcode.append(self.removezeros(admcodepart[self.ignoreleadingcharacters:]))
            locationcode = admcode[0]
            if self.ignore0locationcode and locationcode == '0':
                continue
            for i in range(1, self.aggregateatadminlevel):
                locationcode = '%s|%s' % (locationcode, admcode[i])
            if self.addlocationcode:
                # Add location code field to GeoJSON
                properties['LocationCode'] = locationcode
            # Add location name field to GeoJSON
            if not self.dontaddlocationamesifpos or not lowestadminnamesunique:
                properties['LocationName'] = self.locationcodetoname[locationcode]

        with open(self.geojson_outputfile, 'w') as outfile:
            json.dump(self.jsondict, outfile, sort_keys=True, indent=1, separators=(',', ':'))

        if lowestadminnamesunique:
            logger.info('Lowest admin level names unique.')
            if self.dontaddlocationamesifpos:
                logger.info('So did not add LocationName field!')


def main(argv):
    logging_config_yaml = script_dir_plus_file('logging_configuration.yml', GeoJSONLocations)
    logging_config_dict = load_yaml(logging_config_yaml)
    logging.config.dictConfig(logging_config_dict)

    config_yaml = ''
    cmdline = 'geojson_locations.py -c <configuration>'
    try:
        opts, args = getopt.getopt(argv,"hc:",["configuration="])
    except getopt.GetoptError:
        logger.info(cmdline)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            logger.info(cmdline)
            sys.exit()
        elif opt in ("-c", "--configuration"):
            config_yaml = arg
    logger.info('Using configuration file %s' % config_yaml)
    config_dict = load_yaml(config_yaml)
    geojson_locations = GeoJSONLocations(config_dict)
    lowestadminnamesunique = geojson_locations.combine_location()
    geojson_locations.output_geojson(lowestadminnamesunique)

if __name__ == "__main__":
   main(sys.argv[1:])