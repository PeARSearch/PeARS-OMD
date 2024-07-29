import sys
import shutil
from glob import glob
from os import listdir
from os.path import join, basename, dirname, realpath
from pathlib import Path

user = sys.argv[1]
src_path = sys.argv[2]

dir_path = dirname(realpath(__file__))

Path(join(dir_path, "app/testdocs/",user)).mkdir(parents=True, exist_ok=True)
Path(join(dir_path, "app/testdocs/",user,"localhost.localdomain")).mkdir(parents=True, exist_ok=True)

doc_path = join(dir_path, "app/testdocs/",user,"localhost.localdomain","Documents")
Path(doc_path).mkdir(parents=True, exist_ok=True)


def write_index(d, content):
    index_path = join(d,"index.html")
    with open(index_path,'w') as index:
        index.write(content+'\n')

user_content = "<omd_index><doc url='localhost.localdomain/' contentType='desktop' convertible='False'><title></title></doc></omd_index>"
write_index(join(dir_path, "app/testdocs/",user),user_content)

localdomain_content = "<omd_index><doc url='Documents/' contentType='folder' convertible='False'><title>Documents</title></doc></omd_index>"
write_index(join(dir_path, "app/testdocs/",user,"localhost.localdomain"),localdomain_content)

documents_content = "<omd_index>\n"

docs = glob(join(src_path,'*txt'))
for doc in docs:
    shutil.copy2(doc, doc_path)
    docname = basename(doc)
    doc_xml = f"<doc url='{docname}' contentType='text/plain' convertible='False'><title>{docname}</title></doc>\n"
    documents_content+=doc_xml

documents_content+="</omd_index>\n"
write_index(doc_path,documents_content)
