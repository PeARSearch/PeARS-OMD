from os.path import join, dirname, realpath
import joblib
from scipy.sparse import load_npz
from app.api.models import Urls

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','pods')


def check_db_vs_npz(pod, verbose=True):
    """
    For a given pod, check whether some docs in the database are 
    missing a row in the .npz matrix. The number of rows in the matrix
    should be the number of urls in the pod + 1.

    Return: the length of the urls in the database and the number of 
    rows in the matrix.
    """
    print(f"\t>>> CHECKING DB VS NPZ FOR POD: {pod.name}")
    urls = Urls.query.filter_by(pod=pod.url).all()
    urls = [url.url for url in urls]
    npz_path = join(pod_dir, pod.url+'.npz')
    vectors = load_npz(npz_path)
    if len(set(urls)) + 1 != vectors.shape[0] and verbose:
        print("\t\t>>> WARNING: Length of URL set in DB != number of rows in npz matrix", len(urls), vectors.shape[0])
    return len(set(urls)), vectors.shape[0]

def check_db_vs_pos(pod, verbose=True):
    """
    For a given pod, check whether somd docs in the database are
    missing their positional index representation. Each url id
    should be found at least once in the positional index.

    Return: the database document ids not found in the positional index.
    """
    print(f"\t>>> CHECKING DB VS POS FOR POD: {pod.name}")
    urls = Urls.query.filter_by(pod=pod.url).all()
    urls = set([url.id for url in urls])
    posix_path = join(pod_dir, pod.url+'.pos')
    posindex = joblib.load(posix_path)
    unique_docs = []
    for token_id in posindex:
        for doc_id, _ in token_id.items():
            unique_docs.append(doc_id)
    unique_docs = set(unique_docs)
    db_docs_not_in_pos = list(urls - unique_docs)
    pos_docs_not_in_db = list(unique_docs - urls)
    if len(db_docs_not_in_pos) != 0 and verbose:
        print(f"\t\t>>> WARNING: Some URLs in DB are not in positional index.")
    if len(pos_docs_not_in_db) != 0 and verbose:
        print(f"\t\t>>> WARNING: Some URLs in positional index are not in DB.")
    return db_docs_not_in_pos, pos_docs_not_in_db




