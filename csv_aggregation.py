#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Aggregate fields in csv by location"""
import copy
import csv
import getopt
import json
import logging.config

import sys

from geojson_locations import GeoJSONLocations
from utilities.loader import script_dir_plus_file, load_yaml

logger = logging.getLogger(__name__)


class CSVAggregation:
    def __init__(self, config: dict):
        self.ignoreblankresponses = config['ignoreblankresponses']
        self.addlocationcode = config['addlocationcode']
        self.questions = config['questions']
        self.answers = config.get('answers', None)
        self.aggregator_list = ['geojson_locationcode']
        self.weightcolumn = config.get('weightcolumn', None)
        self.weightfunction = config.get('weightfunction', None)
        self.csv_outputfile = config['csv_aggregated_file']

        headers = ['Question', 'Location Name', 'Answer', 'Count']
        self.questionCol = headers.index('Question')
        self.answerCol = headers.index('Answer')
        self.locationCodeCol = headers.index('Location Name')
        self.countCol = headers.index('Count')
        if self.addlocationcode:
            self.headers = ['Question', 'Location Code', 'Location Name', 'Answer', 'Count']
            self.locationNameCol = self.headers.index('Location Name')
        else:
            self.headers = headers
            self.locationNameCol = self.locationCodeCol

        with open(config['csv_locations_file'], 'r') as csvfile:
            self.contents = list(list(rec) for rec in csv.reader(csvfile))

    def findCol(self, question):
        return self.contents[0].index(question)

    def findDistinctValues(self, agg):
        col = self.findCol(agg)
        output = []
        for d in self.contents[1:]:
            if d[col] not in output:
                output.append(d[col])
        return output

    def genAggObj(self, aggList, tree, initialvalue):
        agg = aggList[0]
        disValues = self.findDistinctValues(agg)
        if len(aggList) > 1:
            tree = self.genAggObj(aggList[1:], tree, initialvalue)
        else:
            tree = initialvalue
        output = {}
        for d in disValues:
            output[d] = copy.deepcopy(tree)
        return output

    def aggQuestions(self, initialvalue, weightfunction):
        self.checkAggLimits(weightfunction, initialvalue)
        output = {}
        aggIDList = []
        for agg in self.aggregator_list:
            aggIDList.append(self.findCol(agg))
        logger.debug(aggIDList)

        for q in self.questions.values():
            output[q] = self.genAggObj(self.aggregator_list + [q], {}, initialvalue)
            qID = self.findCol(q)
            for d in self.contents[1:]:
                ref = output[q]
                for a in aggIDList:
                    ref = ref[d[a]]
                ref[d[qID]] += weightfunction(d)

        return output

    def checkAggLimits(self, weightfunction, initialvalue):
        output = self.genAggObj(self.aggregator_list, {}, initialvalue)
        aggIDList = []
        for agg in self.aggregator_list:
            aggIDList.append(self.findCol(agg))

        for d in self.contents[1:]:
            ref = output
            for a in aggIDList[:-1]:
                ref = ref[d[a]]
            ref[d[aggIDList[len(aggIDList) - 1]]] += weightfunction(d)
        logger.debug(output)

    @staticmethod
    def flattenOutput(data, output, line):
        for key in data:
            if type(data[key]) is dict:
                CSVAggregation.flattenOutput(data[key], output, line + [key])
            else:
                lineLast = copy.copy(line)
                lineLast.append(key)
                lineLast.append(data[key])
                output.append(lineLast)
        return output

    def aggregate(self):
        csv_locationcode_index = self.findCol(self.aggregator_list[0])
        geojson_locationname_index = self.findCol('geojson_locationname')
        csv_locationname_index = self.findCol('csv_locationname')
        locationcodetoname = dict()
        for row in self.contents[1:]:
            locationname = row[geojson_locationname_index]
            if not locationname:
                locationname = row[csv_locationname_index]
            locationcodetoname[row[csv_locationcode_index]] = locationname
        if self.weightcolumn:
            weight_index = self.findCol(self.weightcolumn)
            if self.weightfunction == "weight":
                def weightfunction(x):
                    return float(x[weight_index])
            elif self.weightfunction == "1/weight":
                def weightfunction(x):
                    weight = float(x[weight_index])
                    if weight == 0.0:
                        return 0.0
                    return 1.0 / weight

            data = self.aggQuestions(0.0, weightfunction)
        else:
            data = self.aggQuestions(0, lambda x: 1)

        output = CSVAggregation.flattenOutput(data, [], [])

        self.output = []
        for row in output:
            answer = row[self.answerCol]
            if answer == '' and self.ignoreblankresponses:
                continue
            if self.answers:
                question = row[self.questionCol]
                answersforquestion = self.answers.get(question, None)
                if answersforquestion:
                    row[self.answerCol] = answersforquestion.get(answer, answer)
            count = row[self.countCol]
            if self.weightcolumn:
                if count == 0.0:
                    count = '0.0'
                else:
                    count = '%f' % count
                row[self.countCol] = count
            locationname = locationcodetoname[row[self.locationCodeCol]]
            if self.addlocationcode:
                row.insert(self.locationNameCol, locationname)
            else:
                row[self.locationNameCol] = locationname
            self.output.append(row)

    def output_csv(self):
        with open(self.csv_outputfile, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.headers)
            writer.writerows(sorted(self.output))


def main(argv):
    logging_config_yaml = script_dir_plus_file('logging_configuration.yml', CSVAggregation)
    logging_config_dict = load_yaml(logging_config_yaml)
    logging.config.dictConfig(logging_config_dict)

    config_yaml = ''
    cmdline = 'csv_aggregation.py -c <configuration>'
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
    csv_aggregation = CSVAggregation(config_dict)
    csv_aggregation.aggregate()
    csv_aggregation.output_csv()

if __name__ == "__main__":
   main(sys.argv[1:])