# twitter store

import os
import time
import json
import twitter
import wikidata
import sqlite3

class TweetStore:
    def __init__(self,auth='twitter_creds.json', db='tweets.db', table='mention',
                      handle='mooglebots', type='status'):
        db_exists = os.path.exists(db)
        self.con = sqlite3.connect(db)
        if not db_exists:
            self.init_db()

        with open(auth) as f:
            creds = json.load(f)
        self.api = twitter.Api(**creds)

        self.handle = handle
        self.table = table

    def __del__(self):
        self.con.close()

    def init_db(self):
        cur = self.con.cursor()
        cur.execute('create table if not exists %s (id int, screenname text, created int, text text)' % self.table)

    def sync_batch(self,batch=200,delay=1):
        cur = self.con.cursor()

        (since_id,) = cur.execute('select max(id) from %s' % self.table).fetchone()
        stats = self.api.GetMentions(since_id=since_id)
        nrets = len(stats)

        print('Fetched %d tweets' % nrets)
        if nrets == 0:
            return 0

        cur.executemany('insert into mention values (?,?,?,?)',
            [(st.id, st.user.screen_name, st.created_at_in_seconds, st.text) for st in stats])
        cur.executemany('insert into convo values (?,?,?)',
            [(st.id, 0, '') for st in stats])
        self.con.commit()

        return nrets
