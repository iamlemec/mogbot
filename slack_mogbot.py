# slack info bot

import time
import slackclient
import wikidata

# api key
with open('creds/slack_token.txt') as f:
    token = f.read().strip()

# connect to server
sc = slackclient.SlackClient(token)

# definer
if sc.rtm_connect():
    while True:
        for msg in sc.rtm_read():
            print(msg)
            if msg['type'] == 'message':
                txt = msg['text']
                chan = msg['channel']
                if txt.startswith('define '):
                    req = txt[7:]
                    info = wikidata.try_to_define(req)
                    if len(info) == 0:
                        reply = 'Sorry, could find anything for %s!' % req
                    elif len(info) == 1:
                        reply = info[0]
                    else:
                        reply = '\n'.join(['%d: %s' % (i+1,x) for (i,x) in enumerate(info)])
                    sc.api_call('chat.postMessage', channel=chan, text=reply)
        time.sleep(1)
else:
    print('Connection Failed, invalid token?')
