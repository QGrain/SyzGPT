import os
from bs4 import BeautifulSoup
import requests
import re
import multiprocessing
from fake_useragent import UserAgent

'''
Query https://syzkaller.appspot.com/upstream/fixed for all bugs that have been fixed and have "C" and "syz" reproducers
Save reproducers to text files
'''

ua = UserAgent()

def request_get(url):
    random_header = {'User-Agent': ua.random}
    return requests.get(url=url, headers=random_header)


files = []
bug_type = "fixed" # ["fixed", "open", "invalid"]
for f in os.listdir(f'./files-{bug_type}'):
    files.append(f.split('-')[0])

def get_reproducers(bug):
    id_name = bug.split('=')[-1]
    if id_name in files:
        print(f'[DEBUG] Cached!! {id_name}')
        return
    try:
        page = request_get("https://syzkaller.appspot.com" + bug)
        soup = BeautifulSoup(page.content, 'html.parser')
        # parse last table in page that has class "list_table"
        table = soup.find_all('table', class_="list_table")[-1]
        # find td that has text "syz", only one
        td = table.find_all('td', text="syz")
        for entry in td:
            # get the href of the link
            link = entry.find('a').get('href')
            page = requests.get("https://syzkaller.appspot.com" + link)
            # bug = files/bug?id=17ee94193810ddc5d820094d4e509d47ad5bf6bc
            # get the id from the bug
            bug_id = bug.split("=")[1]
            # link = /text?tag=ReproSyz&x=1789e141d00000
            # get the x from the link
            x = re.search(r'x=(.*)', link).group(1)
            print("Saving bug " + bug_id + " with x " + x)
            with open(f"files-{bug_type}/" + bug_id + "-" + x + ".txt", 'w+') as f:
                f.write(page.text)
    except:
        pass

def main():
    # Query the page
    bugs = []
    page = requests.get(f"https://syzkaller.appspot.com/upstream/{bug_type}")
    soup = BeautifulSoup(page.content, 'html.parser')
    # parse table rows
    rows = soup.find_all('tr')
    for row in rows:
        # print row with class as "title" and first "stat"
        title = row.find_all('td', class_="title")
        stat = row.find_all('td', class_="stat")
        # if title and stat exist
        if title and stat:
            # check if stat[0] contains "C" in "td"
            if "C" in stat[0] or "syz" in stat[0]:
                print(title[0].find('a').get('href'))
                bugs.append(title[0].find('a').get('href'))

    # for each bug, get the reproducers from "https://syzkaller.appspot.com/$bug"
    # run the following code in 15 parallel processes to speed up
    pool = multiprocessing.Pool(1)
    pool.map(get_reproducers, bugs)

if __name__ == "__main__":
    main()