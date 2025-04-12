import os
import json


def read_name(doc_fn):
    with open(doc_fn, 'r') as f:
        d = json.load(f)
    try:
        name = d["NAME"]
    except:
        name = ''
        print('[DEBUG] %s has no NAME section'%doc_fn)
    return name


def parse_name(name_str):
    homo = []
    if name_str == '':
        return homo
    if name_str[0] == '"':
        name_str = name_str[1:]
    if name_str[-1] == '"':
        name_str = name_str[:-1]
    splt = name_str.split(' - ')
    if len(splt) == 2:
        for n in splt[0].split(','):
            n = n.strip()
            if n:
                homo.append(n)
    return homo


def main():
    man_docs_dir = './man_docs'
    homos = []
    for fn in os.listdir(man_docs_dir):
        if fn == 'all_syscall_doc.json':
            continue
        doc_fn = os.path.join(man_docs_dir, fn)
        name = read_name(doc_fn)
        homologous = parse_name(name)
        if len(homologous) > 1 and homologous not in homos:
            homos.append(homologous)
            print(homologous)
    with open('homo_syscalls.json', 'w') as f:
        json.dump(homos, f, indent=4)
    print('[OK] Store %d homo sets at homo_syscalls.json'%len(homos))

if __name__ == '__main__':
    main()