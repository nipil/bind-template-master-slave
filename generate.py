#!/usr/bin/env python3

import argparse
import logging

class App:

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='Generates Bind9 master-slave configurations')
        self.parser.add_argument(
            '-o',
            '--output-dir',
            metavar='DIR',
            default='.')
        self.parser.add_argument(
            'config',
            metavar='CONFIG')
        self.parser.add_argument(
            '-l',
            '--log-level',
            metavar='LVL',
            type=self.__class__.is_log_level_valid,
            default='WARNING')

    @staticmethod
    def is_log_level_valid(level_string):
        if level_string.upper() not in { 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' }:
            raise argparse.ArgumentTypeError('Invalid log level %s' % level_string)
        return level_string.upper()

    def manage_args(self):
        self.args = self.parser.parse_args()
        numeric_level = getattr(logging, self.args.log_level)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        logging.basicConfig(
            format='%(asctime)s %(levelname)s %(message)s',
            level=numeric_level)
        logging.debug('Parsed arguments: %s' % self.args)
        logging.info('Reading configuration from %s' % self.args.config)
        logging.info('Output directory is %s' % self.args.output_dir)

    def load_configuration(self):

        pass

    def run(self):
        self.manage_args()
        self.load_configuration()

if __name__ == '__main__':
    app = App()
    app.run()
    logging.debug()
