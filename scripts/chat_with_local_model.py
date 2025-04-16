import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import openai
from generator.utils import *
from generator.gpt_wrapper import *
try:
    from private_config import *
except ImportError:
    from config import *



if __name__ == '__main__':
    openai.proxy = None
    local_server_ip = '10.26.9.16'
    local_port = 38950
    openai.base_url = 'http://%s:%d/v1/'%(local_server_ip, local_port)
    openai.api_key = 'EMPTY'
    model = 'CodeLlama-7b-Instruct-hf'

    msg_with_hist = [{"role": "system", "content": "You are an expert of Linux Kernel and Syzkaller Fuzzing."}]
    while 1:
        query = input('[Query]: ')
        if query.strip() == 'exit' or query.strip() == 'quit':
            break
        res, total_tokens = query_with_history(msg_with_hist, query, model, True)
        print('[%d tokens] [Response]: %s'%(total_tokens, res))