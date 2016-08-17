# interface to wikidata

import json
from urllib.request import urlopen
from urllib.parse import urlencode

api_base = 'https://www.wikidata.org/w/api.php'

def json_extract(d, path):
    for s in path:
        if s in d:
            d = d[s]
        else:
            return
    return d

def get_text(d, path, lang='en'):
    if type(path) is str:
        path = [path]
    return json_extract(d, path + [lang, 'value'])

def assert_claim(ent, prop, targ):
    for (p,claims) in ent['claims'].items():
        if p == prop:
            for t in claims:
                if json_extract(t, ['mainsnak', 'datavalue', 'value', 'id']) == targ:
                    return True
    return False

def wd_api_call(qdict):
    targ = '%s?%s' % (api_base, urlencode(qdict))
    with urlopen(targ) as f:
        txt = f.read()
        dat = json.loads(txt.decode('utf-8'))
        return dat

def wd_search(s):
    return wd_api_call({
        'action': 'wbsearchentities',
        'format': 'json',
        'search': s,
        'language': 'en'
    })

def wd_entities(ids):
    return wd_api_call({
        'action': 'wbgetentities',
        'format': 'json',
        'ids': '|'.join(ids),
        'languages': 'en',
        'props': 'labels|descriptions|claims'
    })

def try_to_define(s):
    ids = []
    dat1 = wd_search(s)
    for ent in dat1['search']:
        ids.append(ent['id'])

    res = []
    dat2 = wd_entities(ids)
    for (q,ent) in dat2['entities'].items():
        if assert_claim(ent, 'P31', 'Q4167410') == False:
            label = get_text(ent, 'labels')
            desc = get_text(ent, 'descriptions')
            if label is not None and desc is not None:
                res.append((label,desc))

    return res
