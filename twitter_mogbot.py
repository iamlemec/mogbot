# twitter info bot

import os
import time
import json
import twitter
import wikidata
import sqlite3
import editdistance
from operator import itemgetter
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

# connection object
class Mogbot:
    def __init__(self,auth='twitter_creds.json', db='tweets.db', handle='mooglebots'):
        db_exists = os.path.exists(db)
        self.con = sqlite3.connect(db)
        if not db_exists:
            self.init_db()

        with open(auth) as f:
            creds = json.load(f)
        self.api = twitter.Api(**creds)

        self.handle = handle

    def __del__(self):
        self.con.close()

    def init_db(self):
        cur = self.con.cursor()
        cur.execute('create table if not exists mention (id int, screenname text, created int, query text)')
        cur.execute('create table if not exists reply (id int, code int, defin text)')

    def sync_batch(self,when='newest'):
        cur = self.con.cursor()

        (max_id,since_id) = cur.execute('select min(id),max(id) from mention').fetchone()
        args = {'since_id': since_id} if when == 'newest' else {'max_id': max_id}
        stats = self.api.GetMentions(**args)
        nrets = len(stats)

        print('Fetched %d tweets' % nrets)
        if nrets == 0:
            return 0

        cur.executemany('insert into mention values (?,?,?,?)',
            [(st.id, st.user.screen_name, st.created_at_in_seconds, st.text) for st in stats])
        cur.executemany('insert into reply values (?,?,?)',
            [(st.id, 0, '') for st in stats])
        self.con.commit()

        return nrets

    def sync_all(self,when='newest'):
        done_old = False
        done_new = False
        for i in range(RATE_LIMIT):
            if not done_old and when in (None,'oldest'):
                nrets = self.sync_batch(when='oldest')
                if nrets == 0:
                    done_old = True
            if not done_new and when in (None,'newest'):
                nrets = self.sync_batch(when='newest')
                if nrets == 0:
                    done_new = True
            if (when == 'oldest' and done_old) or (when == 'newest' and done_new) or (when is None and done_old and done_new):
                return True
        return False

    def reply_batch(self,batch=15,post=True):
        cur = self.con.cursor()

        store = {}
        for (id,name,text) in cur.execute('select id,screenname,query from (select * from reply where code=0 limit ?) left join mention using(id) order by created', (batch,)):
            msg = look_for(text,'@%s' % self.handle)
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
                        reply = '@%s %s' % (name,replies[0])
                        for i in range(1, len(replies)):
                            if len(reply) > TWEET_MAX:
                                break
                            reply += '\n%s' % replies[i]
                        reply = clamp_tweet(reply)

                    # store results
                    if post:
                        self.api.PostUpdate(reply, in_reply_to_status_id=id)
                        cur.execute("update reply set code=1,defin=? where id=?", (reply, id))
                    else:
                        print(term)
                        print(reply)
                        print()

        # commit changes
        if post:
            self.con.commit()
