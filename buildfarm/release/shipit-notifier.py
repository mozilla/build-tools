#!/usr/bin/env python
"""shipit-agent.py [options]

Listens for buildbot release messages from pulse and then sends them
to the shipit REST API."""

import uuid
import site
import datetime
import pytz

from optparse import OptionParser
from ConfigParser import ConfigParser
from release.info import getReleaseName
from mozillapulse import consumers
from mozillapulse import config as pconf
from os import path
from dateutil import parser

import sys
sys.path.insert(0, path.join(path.dirname(__file__), "../../lib/python"))
from kickoff.api import Status

import logging as log

NAME_KEYS = (u'product', u'version', u'build_number')
PROPERTIES_KEYS = (u'platform', u'chunkTotal', u'chunkNum', u'event_group')


def receive_message(config, data, message):
    try:
        if not data['payload']['build'].get(u'builderName').\
                                        startswith('release-'):
            return
        if ' test ' in data['payload']['build'].get(u'builderName'):
            return
        if not data['payload']['build'].get('properties'):
            log.error('TypeError: build properties not found - {}'.\
                      format(data['payload']['build'].get('builderName')))
            return
        if data['payload'][u'results'] != 0:
            return

        log.info('msg received - {}'.format(data['payload']['build'].\
                                     get(u'builderName')))

        payload = {}
        payload[u'sent'] = data['_meta'].get(u'sent')
        payload[u'results'] = data['payload'].get(u'results')
        payload[u'event_name'] = data['payload']['build'].get(u'builderName')

        # Convert sent to UTC
        timestamp = parser.parse(payload[u'sent']).astimezone(pytz.utc)
        payload[u'sent'] = unicode(timestamp.strftime('%Y-%m-%d %H:%M:%S'))

        for key in PROPERTIES_KEYS:
            for prop in data['payload']['build'].get('properties'):
                if prop[0] == key:
                    try:
                        payload[key] = prop[1]
                    except IndexError as e:
                        payload[key] = 'None'
                        log.warning('{} not in build properties for {} - {}'.\
                                    format(key, payload['event_name'], e))
        payload[u'group'] = payload.pop(u'event_group')
        if 'postrelease' in payload[u'event_name']:
            payload[u'group'] = 'postrelease'

        name = {}
        for key in NAME_KEYS:
            for prop in data['payload']['build'].get('properties'):
                if prop[0] == key:
                    try:
                        name[key] = prop[1]
                    except IndexError as e:
                        name[key] = 'None'
                        log.warning('{} not in build properties for {} - {}'.\
                                    format(key, payload['event_name'], e))
        name = getReleaseName(name.pop('product'), 
                              name.pop('version'), 
                              name.pop('build_number'))

        log.info('adding new release event for {} with event_name {}'.\
                 format(name, payload['event_name']))
        status_api = Status((config.get('api', 'username'), 
                             config.get('api', 'password')), 
                            api_root=config.get('api', 'api_root'))
        status_api.update(name, data=payload)
        print payload
    except Exception as e:
        log.error('{} - {}'.format(e, data['payload']['build'].get('builderName')))
    finally:
        message.ack()


def main():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="config",
                      help="Configuration file")
    options = parser.parse_args()[0]
    config = ConfigParser()
    try:
        config.read(options.config)
    except:
        parser.error("Could not open configuration file")

    def got_message(*args, **kwargs):
        receive_message(config, *args, **kwargs)

    if not options.config:
        parser.error('Configuration file is required')

    verbosity = {True: log.DEBUG, False: log.WARN}
    log.basicConfig(
        format='%(asctime)s %(message)s',
        level=verbosity[config.getboolean('shipit-notifier', 'verbose')]
    )

    # Adjust applabel when wanting to run shipit on multiple machines
    pulse = consumers.BuildConsumer(applabel='shipit-notifier', ssl=False)
    pulse.configure(topic='build.#.finished',
                    durable=True, callback=got_message)

    log.info('listening for pulse messages')
    pulse.listen()

if __name__ == "__main__":
    main()
