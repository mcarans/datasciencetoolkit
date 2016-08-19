#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Create location code after merging location fields in csv"""
import copy
import csv
import getopt
import json
import logging.config

import sys

from geojson_locations import GeoJSONLocations
from utilities.loader import script_dir_plus_file, load_yaml

logger = logging.getLogger(__name__)


class CSVLocations:
    def __init__(self, config: dict, geojson_locations):
        self.matchonlocationcodeandname = config.get('matchonlocationcodeandname', False)
        self.aggregateatadminlevel = config['aggregateatadminlevel']
        self.alternateadmname = config['alternateadmname']
        self.csv_admcode = config['csv_admcode']
        self.csv_admname = config['csv_admname']
        if self.alternateadmname:
            self.csv_admnamealt = config['csv_admnamealt']
        self.csv_locations_file = config['csv_locations_file']
        self.errors_outputfile = config['errors_outputfile']
        self.questions = config['questions']
        self.geojson_locations = geojson_locations
        self.weightcol = config.get('weightcolumn', None)
        self.filtercolumn = config.get('filtercolumn', None)
        self.filterby = config.get('filterby', None)


        with open(config['csv_inputfile'], 'r') as csvfile:
            self.contents = list(list(rec) for rec in csv.reader(csvfile, delimiter=config['csv_inputdelimiter']))

        self.locationcodetoname = dict()
        self.locationnametocode = dict()
        self.locationcodetonamealt = dict()
        self.locationnametocodealt = dict()

        self.locationsnotisgeojson = dict()
        self.locationcodemismatches = dict()
        self.locationcodeadm1admlowestmismatches = dict()
        self.locationcodeadm1admswitchmismatches = dict()
        self.output = []
        self.headers = []

    def add_csvlocationcode(self):
        header = self.contents[0]
        header.append('csv_locationcode')
        admcode_index = []
        admname_index = []
        for i in range(0, self.aggregateatadminlevel):
            admcode_index.append(header.index(self.csv_admcode[i]))
            admname_index.append(header.index(self.csv_admname[i]))
        if self.alternateadmname:
            admnamealt_index = []
            for i in range(0, self.aggregateatadminlevel):
                admnamealt_index.append(header.index(self.csv_admnamealt[i]))
        for row in self.contents[1:]:
            admcode = []
            admname = []
            for i in range(0, self.aggregateatadminlevel):
                admcode.append(GeoJSONLocations.removezeros(row[admcode_index[i]]))
                admname.append(row[admname_index[i]])
            if self.alternateadmname:
                admnamealt = []
                for i in range(0, self.aggregateatadminlevel):
                    admnamealt.append(row[admnamealt_index[i]])
    
            locationcode = admcode[0]
            locationname = admname[0]
            for i in range(1, self.aggregateatadminlevel):
                locationcode = '%s|%s' % (locationcode, admcode[i])
                locationname = '%s|%s' % (locationname, admname[i])
            if self.alternateadmname:
                locationnamealt = admnamealt[0]
                for i in range(1, self.aggregateatadminlevel):
                    locationnamealt = '%s|%s' % (locationnamealt, admnamealt[i])
            row.append(locationcode)
            self.locationcodetoname[locationcode] = locationname
            self.locationnametocode[locationname.lower()] = locationcode
            if self.alternateadmname:
                self.locationcodetonamealt[locationcode] = locationnamealt
                self.locationnametocodealt[locationnamealt.lower()] = locationcode

    def add_geoJSONlocationcodename(self):
        cutdown_headers = []
        for fieldname in self.csv_admcode:
            cutdown_headers.append(fieldname)
        for fieldname in self.csv_admname:
            cutdown_headers.append(fieldname)
        if self.alternateadmname:
            for fieldname in self.csv_admnamealt:
                if fieldname not in cutdown_headers:
                    cutdown_headers.append(fieldname)
        if self.weightcol:
            cutdown_headers.append(self.weightcol)
        self.headers = ['csv_locationcode', 'csv_locationname', 'geojson_locationcode', 'geojson_locationname'] + cutdown_headers
        for fieldname in self.questions:
            cutdown_headers.append(fieldname)
            self.headers.append(self.questions[fieldname])
        for row in self.contents[1:]:
            if self.filtercolumn:
                if row[self.contents[0].index(self.filtercolumn)] != self.filterby:
                    continue
            output_row = []
            for fieldname in cutdown_headers:
                output_row.append(row[self.contents[0].index(fieldname)])
            csv_locationcode = row[self.contents[0].index('csv_locationcode')]
            output_row.insert(self.headers.index('csv_locationcode'), csv_locationcode)
            csv_locationname = self.locationcodetoname[csv_locationcode]
            output_row.insert(self.headers.index('csv_locationname'), csv_locationname)

            geojson_locationname = self.geojson_locations.locationcodetoname.get(csv_locationcode)
            if geojson_locationname and self.matchonlocationcodeandname:
                if geojson_locationname.lower() not in csv_locationname.lower():
                    geojson_locationname = None
            if geojson_locationname:
                geojson_locationcode = csv_locationcode
            else:
                csv_locationnamealt = ''
                geojson_locationcode = self.geojson_locations.locationnametocode.get(csv_locationname.lower())
                if self.alternateadmname and not geojson_locationcode:
                    csv_locationnamealt = self.locationcodetonamealt[csv_locationcode]
                    geojson_locationcode = self.geojson_locations.locationnametocode.get(csv_locationnamealt.lower())
                if geojson_locationcode:
                    geojson_locationname = self.geojson_locations.locationcodetoname[geojson_locationcode]
                    geojson_locationfullname = self.geojson_locations.locationcodetofullname[geojson_locationcode]
                    self.locationcodemismatches[csv_locationcode] = (csv_locationname, csv_locationnamealt, geojson_locationcode, geojson_locationfullname)
                else:
                    admname = csv_locationname.split('|')
                    locationadm1admlowestname = '%s|%s' % (admname[0], admname[len(admname)-1])
                    geojson_locationcode = self.geojson_locations.locationnameadm1admlowesttocode.get(locationadm1admlowestname.lower())
                    if self.alternateadmname and not geojson_locationcode:
                        admname = csv_locationnamealt.split('|')
                        locationadm1admlowestnamealt = '%s|%s' % (admname[0], admname[len(admname) - 1])
                        geojson_locationcode = self.geojson_locations.locationnameadm1admlowesttocode.get(locationadm1admlowestnamealt.lower())
                    if geojson_locationcode:
                        geojson_locationname = self.geojson_locations.locationcodetoname[geojson_locationcode]
                        geojson_locationfullname = self.geojson_locations.locationcodetofullname[geojson_locationcode]
                        self.locationcodeadm1admlowestmismatches[csv_locationcode] = (csv_locationname, csv_locationnamealt, geojson_locationcode, geojson_locationfullname)
                    else:
                        geojson_locationcode = self.geojson_locations.locationnameadm1admswitchtocode.get(locationadm1admlowestname.lower())
                        if self.alternateadmname and not geojson_locationcode:
                            geojson_locationcode = self.geojson_locations.locationnameadm1admswitchtocode.get(locationadm1admlowestnamealt.lower())
                        if geojson_locationcode:
                            geojson_locationname = self.geojson_locations.locationcodetoname[geojson_locationcode]
                            geojson_locationfullname = self.geojson_locations.locationcodetofullname[geojson_locationcode]
                            self.locationcodeadm1admswitchmismatches[csv_locationcode] = (csv_locationname, csv_locationnamealt, geojson_locationcode, geojson_locationfullname)
                        else:
                            geojson_locationcode = ''
                            geojson_locationname = ''
                            self.locationsnotisgeojson[csv_locationcode] = csv_locationname

            output_row.insert(self.headers.index('geojson_locationcode'), geojson_locationcode)
            output_row.insert(self.headers.index('geojson_locationname'), geojson_locationname)
            self.output.append(output_row)

    def output_csv(self):
        with open(self.csv_locations_file, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.headers)
            writer.writerows(sorted(self.output))

    def output_errors(self):
        with open(self.errors_outputfile, 'w') as outputfile:
            outputfile.write('Missing locations\n')
            for missinglocationcode in self.locationsnotisgeojson:
                outputfile.write('csv: location code - %s, location name = %s\n' % (
                missinglocationcode, self.locationsnotisgeojson[missinglocationcode]))
            outputfile.write('Location Code Mismatches (admin1|...adminN)\n')
            for mismatchcode in self.locationcodemismatches:
                mismatchvalues = self.locationcodemismatches[mismatchcode]
                outputfile.write(
                    'csv: location code - %s, location name = %s, alternate location name = %s    geojson: location code - %s, location name = %s\n' % (
                        mismatchcode, mismatchvalues[0], mismatchvalues[1], mismatchvalues[2], mismatchvalues[3]))
            outputfile.write('Location Code Mismatches on admin levels 1 and N only (admin1|adminN)\n')
            for mismatchcode in self.locationcodeadm1admlowestmismatches:
                mismatchvalues = self.locationcodeadm1admlowestmismatches[mismatchcode]
                outputfile.write(
                    'csv: location code - %s, location name = %s, alternate location name = %s    geojson: location code - %s, location name = %s\n' % (
                        mismatchcode, mismatchvalues[0], mismatchvalues[1], mismatchvalues[2], mismatchvalues[3]))
            outputfile.write('Location Code Mismatches on admin levels 1 and N+1 (switched with N) only (admin1|adminN+1)\n')
            for mismatchcode in self.locationcodeadm1admswitchmismatches:
                mismatchvalues = self.locationcodeadm1admswitchmismatches[mismatchcode]
                outputfile.write(
                    'csv: location code - %s, location name = %s, alternate location name = %s    geojson: location code - %s, location name = %s\n' % (
                        mismatchcode, mismatchvalues[0], mismatchvalues[1], mismatchvalues[2], mismatchvalues[3]))


def main(argv):
    logging_config_yaml = script_dir_plus_file('logging_configuration.yml', CSVLocations)
    logging_config_dict = load_yaml(logging_config_yaml)
    logging.config.dictConfig(logging_config_dict)

    config_yaml = ''
    cmdline = 'csv_locations.py -c <configuration>'
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
    geojson_locations.combine_location()
    csv_locations = CSVLocations(config_dict, geojson_locations)
    csv_locations.add_csvlocationcode()
    csv_locations.add_geoJSONlocationcodename()
    csv_locations.output_csv()
    csv_locations.output_errors()

if __name__ == "__main__":
   main(sys.argv[1:])