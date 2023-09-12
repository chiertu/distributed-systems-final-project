import codecs

import dill

ENCODING = 'base64'


def serialize(obj):
    return codecs.encode(dill.dumps(obj), ENCODING).decode()


def deserialize(obj):
    return dill.loads(codecs.decode(obj.encode(), ENCODING))