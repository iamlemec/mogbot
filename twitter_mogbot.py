# twitter info bot

import os
import sys
import time
import json
import wikidata
import sqlite3
import editdistance
from operator import itemgetter
from queue import Queue
from time import sleep
import tweepy

# constants
TWEET_MAX = 140
RATE_LIMIT = 15
DIST_CUTOFF = 0.5

# utils
def levenshtein(a,b):
    return editdistance.eval(a,b)/max(len(a),len(b))

def clamp_tweet(txt,size=TWEET_MAX):
    if len(txt) > size:
        return '%s…' % txt[:size-1]
    else:
        return txt

def look_for(txt,cmd):
    cstr = '%s ' % cmd
    if txt.startswith(cstr):
        return txt[len(cstr):]
    else:
        return None

class MogbotListener(tweepy.StreamListener):
    def __init__(self, mogbot):
        super().__init__()
        self.mogbot = mogbot

    def on_status(self, status):
        self.mogbot.on_mention(status)

class MogbotLogger(tweepy.StreamListener):
    def __init__(self, mogbot):
        super().__init__()
        self.mogbot = mogbot

    def on_status(self, status):
        self.mogbot.on_reply(status)

# connection object
class Mogbot:
    def __init__(self,auth='twitter_creds.json', db='tweets.db', handle='mooglebots'):
        db_exists = os.path.exists(db)
        self.con = sqlite3.connect(db)
        if not db_exists:
            self.init_db()
        self.queue = Queue()

        with open(auth) as f:
            creds = json.load(f)
        auth = tweepy.OAuthHandler(creds['consumer_key'], creds['consumer_secret'])
        auth.set_access_token(creds['access_token_key'], creds['access_token_secret'])
        self.api = tweepy.API(auth)

        self.logger = MogbotLogger(self)
        self.stream_logger = tweepy.Stream(auth=self.api.auth, listener=self.logger)

        self.listener = MogbotListener(self)
        self.stream_listener = tweepy.Stream(auth=self.api.auth, listener=self.listener)

        self.handle = handle

    def __del__(self):
        self.con.close()

    def init_db(self):
        cur = self.con.cursor()
        cur.execute('create table if not exists tweet (id int, handle text, created int, text text, reply int)')

    def store_tweet(self, status):
        self.queue.put((status.id, status.user.screen_name, status.timestamp_ms, status.text, status.in_reply_to_status_id))

    def empty_queue(self):
        if self.queue.qsize() == 0:
            return
        cur = self.con.cursor()
        while True:
            x = self.queue.get()
            if x is None:
                break
            cur.execute('insert into tweet values (?,?,?,?,?)', x)
            self.con.commit()

    def run(self):
        self.stream_logger.userstream(async=True)
        self.stream_listener.filter(track=['@%s' % self.handle],async=True)
        try:
            while True:
                self.empty_queue()
                sleep(1)
        except KeyboardInterrupt:
            print('exiting')
            sys.exit()

    def build_reply(self, text, name):
        msg = look_for(text, '@%s' % self.handle)
        if msg is not None:
            term = look_for(msg, 'define')
            if term is not None:
                # generate reply
                info = wikidata.try_to_define(term)
                if len(info) == 0:
                    reply = 'Sorry, could find anything for %s!' % req
                else:
                    order = sorted([(l, d, levenshtein(l, term)) for (l, d) in info], key=itemgetter(2))
                    replies = ['%s: %s' % (l, d) for (l, d, x) in order if x < DIST_CUTOFF]
                    lengths = [len(r) for r in replies]
                    reply = '@%s\n%s' % (name,replies[0])
                    for i in range(1, len(replies)):
                        if len(reply) > TWEET_MAX:
                            break
                        reply += '\n%s' % replies[i]
                    reply = clamp_tweet(reply)
                return reply

    def on_mention(self, status):
        print('QUERY')
        print(status.text)
        print()

        # store query
        self.store_tweet(status)

        # generate definition and tweet
        reply = self.build_reply(status.text, status.user.screen_name)
        if reply is not None:
            self.api.update_status(reply, in_reply_to_status_id=status.id)


    def on_reply(self, status):
        if status.user.screen_name != self.handle:
            return

        print('REPLY')
        print(status.text)
        print()

        # store reply
        self.store_tweet(status)

if __name__ == '__main__':
    mog = Mogbot()
    mog.run()
