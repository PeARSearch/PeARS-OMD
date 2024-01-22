import re
import sys
from glob import glob

def write_doc(doc,filename):
    with open(filename,'w') as f:
        f.write(doc+'\n')

def extract_docs(doc_file, n):
    with open(doc_file) as df:
        doc = ''
        ndocs = 0
        for l in df:
            l=l.rstrip('\n')
            if l[:4] == "<doc":
                m = re.search('title=\"([^\"]*)\"',l)
                title = m.group(1).split('/')[-1]
            elif "</doc" not in l:
                if len(doc.split()) < 100:
                    doc+=l+' '
            else:
                if len(doc.split()) > 50:
                    write_doc(doc,title.replace(' ','_')+'.txt')
                    ndocs+=1
                    if ndocs > n:
                        break
                doc = ''

def generate_index_file():
    with open('index.html','w') as f:
        f.write('<omd_index>')
        filenames = glob('*.txt')
        for filename in filenames:
            f.write('<doc url="'+filename+'" contentType="text/plain"><title>'+filename.replace('.txt','').replace('_',' ')+'</title></doc>')
        f.write('</omd_index>'+'\n')

extract_docs(sys.argv[1],int(sys.argv[2]))
generate_index_file()
