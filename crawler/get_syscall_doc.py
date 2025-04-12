import os, random, requests, json
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from time import time, sleep


ua = UserAgent()


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False
        
def save_doc(doc, path):
    check_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f)

        
def request_get(url):
    requests.packages.urllib3.disable_warnings()
    random_header = {'User-Agent': ua.random}
    return requests.get(url=url, headers=random_header, verify=False)


def get_syscall_list():
    syscall_list = []
    url = 'https://man7.org/linux/man-pages/dir_section_2.html'
    r = request_get(url)
    soup = BeautifulSoup(r.text, 'lxml')
    tables = soup.find_all('table')
    tds = tables[1].find_all('td')
    for td in tds:
        a_list = td.find_all('a')
        for a in a_list:
            syscall_list.append(a.text.split('(2)')[0].strip())
    return syscall_list


def get_syscall_doc(syscall):
    url = 'https://man7.org/linux/man-pages/man2/' + syscall + '.2.html'
    r = request_get(url)
    soup = BeautifulSoup(r.text, 'lxml')

    headers = []
    for h2 in soup.find_all('h2'):
        h2_text = h2.text.split(' \xa0')[0].strip()
        headers.append(h2_text)
    #print(headers)

    syscall_doc = {}
    for h in headers:
        syscall_doc[h] = ''

    i = 0
    for pre in soup.find_all('pre'):
        pre_text = pre.text.strip()
        if i == 0:
            # ignore the first pre section
            pass
        else:
            syscall_doc[headers[i-1]] = pre_text
        i += 1
    return syscall_doc


def print_doc(syscall_doc, syscall):
    print('%s' % syscall)
    for sysk in syscall_doc[syscall]:
        print('%s:\n%s' % (sysk, syscall_doc[syscall][sysk]))


def main():
    start_t = time()
    doc_dir = './man_docs'
    syscall_list_path = './syscall_from_manpage.txt'
    
    syscall_list = get_syscall_list()
    print('[%.2f][√] Get the latest syscall list'%(time()-start_t))
    with open(syscall_list_path, 'w', encoding='utf-8') as f:
        for syscall in syscall_list:
            f.write('%s\n'%syscall)
    print('[%.2f][√] Store the latest syscall list at %s'%(time()-start_t, syscall_list_path))
    
    # syscall_list = []
    # with open(syscall_list_path, 'r', encoding='utf-8') as f1:
    #     for line in f1.readlines():
    #         line = line.strip()
    #         if line:
    #             syscall_list.append(line.split('(2)')[0])

    all_syscall_doc = {}
    secure_sleep = 1
    for k, syscall in enumerate(syscall_list):
        syscall_doc = get_syscall_doc(syscall)
        all_syscall_doc[syscall] = syscall_doc
        doc_path = os.path.join(doc_dir, '%s.json'%syscall)
        save_doc(syscall_doc, doc_path)
        print('[%.2f][√] Get %d doc: %s, secure sleep %ss'%(time()-start_t, k, syscall, secure_sleep))
        sleep(secure_sleep)

    save_doc(all_syscall_doc, os.path.join(doc_dir, 'all_syscall_doc.json'))
    print('[%.2f][√] Done! All syscall docs are stored at %s'%(time()-start_t, doc_dir))

if __name__ == '__main__':
    main()
