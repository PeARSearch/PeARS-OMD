import joblib
from os.path import join, dirname, realpath
from app import models

def load_posix(pod_path):
    dir_path = dirname(dirname(realpath(__file__)))
    posix_path = join(dir_path,'pods')
    posix = joblib.load(join(posix_path,pod_path+'.pos'))
    return posix

def dump_posix(posindex, pod_path):
    dir_path = dirname(dirname(realpath(__file__)))
    posix_path = join(dir_path,'pods')
    joblib.dump(posindex, join(posix_path,pod_path+'.pos'))


def posix_doc(text, doc_id, pod_path):
    lang = pod_path.split('/')[2]
    posindex = load_posix(pod_path)
    vocab = models[lang]['vocab']
    for pos, token in enumerate(text.split()):
        if token not in vocab:
            continue
        token_id = vocab[token]
        if doc_id in posindex[token_id]:
            posindex[token_id][doc_id] += f"|{pos}"
        else:
            posindex[token_id][doc_id] = f"{pos}"
    dump_posix(posindex, pod_path)
