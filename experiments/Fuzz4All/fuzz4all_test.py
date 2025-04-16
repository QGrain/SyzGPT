import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import openai
from generator.utils import *
from generator.gpt_wrapper import *
try:
    from private_config import *
except ImportError:
    from config import *


def read_file_content(doc_path):
    with open(doc_path, 'r') as f:
        return f.read()
    


def step1(client):
    syz_syntax_doc = read_file_content('/root/fuzzers/SyzGPT-fuzzer/docs/program_syntax.md')
    msg_with_hist = [{"role": "system", "content": "You are an auto-prompting tool"}]

    query = syz_syntax_doc + '\n' + "Please summarize the above documentation in a concise manner to describe the usage and functionality of the target "
    res, total_tokens = query_with_history_new(client, msg_with_hist, query, LLM_MODEL, True)
    print('[%d tokens] [Response]: %s'%(total_tokens, res))
    return res


def step2(client, syscall='', docstring='', example_code='', seperator='', begin=''):
    # docstring = step1(client)
    docstring = read_file_content('./fuzz4all_configs/docstring')
    seperator = 'Please create a very short syz-program for syscall %s which uses syzlang features in a complex way'%syscall
    msg_with_hist = [{"role": "system", "content": "You are a Syz-program fuzzer"}]

    query = f"/* {docstring} */\n"
    if example_code != '':
        query += f"example program:\n{example_code}\n"
    query += f"{seperator}\n"
    if begin != '':
        query += f"{begin}"
    res, total_tokens = query_with_history_new(client, msg_with_hist, query, LLM_MODEL, True)
    if example_code != '':
        out_path = os.path.join('./fuzz4all_outputs', 'with_example', syscall)
    else:
        out_path = os.path.join('./fuzz4all_outputs', 'no_example', syscall)
    with open(out_path, 'w') as f:
        f.write(res)
    return res, total_tokens


if __name__ == '__main__':
    t0 = time.time()
    client = OpenAI(
        api_key=API_KEY,
        http_client=httpx.Client(proxies=proxies['http'])
    )
    
    with open('data/sampled_variants.txt', 'r') as f:
        sampled_variants = [line.strip() for line in f.readlines()]
    # example_prog = read_file_content('fuzz4all_configs/example.prog')
    example_prog = ''
    cnt = 0
    total_tks = 0
    for syscall in sampled_variants:
        _, tks = step2(client, syscall, example_code=example_prog)
        total_tks += tks
        cnt += 1
        print('[%d] Done for %s, cost %d tokens'%(cnt, syscall, tks))
    print('Cost %.2fs, %d tokens in total'%(time.time()-t0, total_tks))