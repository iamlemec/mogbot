# twitter store

import os
import time
import json
import twitter
import wikidata
import sqlite3

class TweetStore:
    def __init__(self,auth='twitter_creds.json', handle, db, table='tweet', type='status'):
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
        cur.execute('create table if not exists %s (id int, created int, handle text, text text, reply int)' % self.table)

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
            [(st.id, st.created_at_in_seconds, st.user.screen_name, st.text, None) for st in stats])
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
