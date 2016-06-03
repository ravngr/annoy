#!/usr/bin/env python3
# -- coding: utf-8 --

import argparse
import datetime
import json
import logging
import logging.config
import os
import random
import sqlite3
import sys
import threading

import sched
import tweepy

import util


__author__ = 'ravngr'
__copyright__ = 'Copyright 2016, Chris Harrison'
__credits__ = ['ravngr']
__license__ = 'MIT'
__version__ = '0.1.0'
__maintainer__ = 'ravngr'
__email__ = 'dev@ravngr.com'
__status__ = 'Prototype'


# Default location of configuration file
_DEFAULT_CONFIG_FILE = 'config.json'

# Constants
_API_LOW_LIMIT = 4
_TWEET_LIMIT = 140

# Dict for application configuration
_app_cfg = {}


class AnnoyException(Exception):
    pass


class AnnoyScheduleThread(threading.Thread):
    pass


def send_tweet(twitter_api, message):
    root_logger = logging.getLogger('tweet')

    cfg_tweet = _app_cfg['tweet']

    # Expand recipient list
    tweet_format = cfg_tweet.pop('format')
    tweet_hashtag = cfg_tweet.pop('hashtag')
    tweet_target = cfg_tweet.pop('target')
    tweet_target_delimiter = cfg_tweet.pop('target_delimiter')

    tweet_target = tweet_target_delimiter.join(["@{}".format(x) for x in tweet_target])

    cfg_tweet['target'] = tweet_target
    cfg_tweet['message'] = message

    tweet = tweet_format.format(**cfg_tweet)

    if len(tweet) > _TWEET_LIMIT:
        raise AnnoyException('Tweet exceeds length limit')

    root_logger.debug("Tweet sent: {}".format(tweet))


def main():
    app_path = os.path.dirname(os.path.realpath(__file__))

    try:
        app_git_hash = util.get_git_hash()
    except OSError:
        app_git_hash = 'not found'

    parse = argparse.ArgumentParser(description='Slightly annoying twitter thing')

    parse.add_argument('-c', '--config', help='Path to config file', dest='config_path',
                       default=os.path.join(app_path, _DEFAULT_CONFIG_FILE))
    parse.add_argument('-d', '--daemon', help='Run as daemon', dest='run_daemon', action='store_true')
    parse.set_defaults(run_daemon=False)

    args = parse.parse_args()

    # Read configuration
    with open(args.config_path, 'r') as f:
        config_dict = json.load(f)
        logging_dict = config_dict.pop('log')

        _app_cfg.update(config_dict)
        logging.config.dictConfig(logging_dict)

    # Setup logging
    root_logger = logging.getLogger('main')
    root_logger.info("annoyb {} | git: {}".format(__version__, app_git_hash))

    for m in [('tweepy', tweepy.__version__)]:
        root_logger.info("{} {}".format(m[0], m[1]))

    root_logger.info("Launch command: {}".format(' '.join(sys.argv)))

    # Check configuration
    if not _app_cfg['twitter_consumer_key'] or not _app_cfg['twitter_consumer_secret']:
        root_logger.error('Twitter API key not configured')
        return

    try:
        # Get twitter authentication
        auth = tweepy.OAuthHandler(_app_cfg['twitter_consumer_key'], _app_cfg['twitter_consumer_secret'])

        if not _app_cfg['twitter_access_token'] or not _app_cfg['twitter_access_token_secret']:
            # Get access token
            root_logger.warning('Attempting to get access token')

            try:
                redirect_url = auth.get_authorization_url()

                print("Access Twitter OAuth URL: {}".format(redirect_url))

                request_token = input('Enter request token: ')

                [access_token, access_token_secret] = auth.get_access_token(request_token)

                print("Access token config: {}".format(json.dumps(
                    {'twitter_access_token': access_token, 'twitter_access_token_secret': access_token_secret},
                    indent=2, separators=(',', ': '))))
            except tweepy.TweepError:
                logging.error('Failed to get Twitter request or access token')
                return

            root_logger.warning('Save authentication token in configuration')
            return

        auth.set_access_token(_app_cfg['twitter_access_token'], _app_cfg['twitter_access_token_secret'])

        # Get handle to Twitter API
        twitter_api = tweepy.API(auth)

        #if not twitter_api.verify_credentials():
        #    root_logger.error('Authentication failed')
        #    return

        limit = twitter_api.rate_limit_status()
        limit = util.dict_tree_walk(limit, 'remaining')

        for key, val in sorted(limit.items()):
            reset_time = datetime.datetime.fromtimestamp(val['reset']).strftime('%c')

            if val['remaining'] == 0:
                root_logger.error("API {} limit hit".format(key))
            elif val['remaining'] <= _API_LOW_LIMIT:
                root_logger.warning("API {} limit low".format(key))

            root_logger.info("API {}: {} of {} remaining (reset at: {})".format(key, val['remaining'], val['limit'], reset_time))

        user = twitter_api.me()
        target = [twitter_api.get_user(user) for user in _app_cfg['tweet']['target']]

        root_logger.info("Authenticated as {} (id: {})".format(user.screen_name, user.id))

        for t in target:
            root_logger.info("Target {} (id: {})".format(t.screen_name, t.id))

            friendship = twitter_api.show_friendship(source_id=user.id, target_id=t.id)

            if friendship[0].blocking:
                root_logger.error("User {} blocking {}".format(friendship[0].screen_name, friendship[1].screen_name))
                return

            if friendship[0].blocked_by:
                root_logger.error("User {} blocked by {}".format(friendship[1].screen_name, friendship[0].screen_name))
                return

            if not friendship[0].following:
                root_logger.warn("User {} not following {}".format(friendship[0].screen_name,
                                                                   friendship[1].screen_name))

            if not friendship[1].following:
                root_logger.warn("User {} not followed by {}".format(friendship[0].screen_name,
                                                                     friendship[1].screen_name))

        # send_tweet(twitter_api, 'Cake')

        # Exit gracefully
        root_logger.info('Exiting normally')
    except:
        root_logger.exception('Unhandled exception', exc_info=True)
        raise


if __name__ == '__main__':
    main()
