import openai
import argparse
from generator.utils import *
from generator.gpt_wrapper import *
try:
    from private_config import *
except ImportError:
    from config import *



if __name__ == '__main__':
    parser = argparse.ArgumentParser('chatbot for test')
    parser.add_argument('-m', '--model', type=str, help='llm model')
    args = parser.parse_args()
    
    llm_model = args.model or LLM_MODEL
    openai.api_key = API_KEY
    openai.proxy = proxies['http']

    msg_with_hist = [{"role": "system", "content": "You are an expert of Linux Kernel and Syzkaller Fuzzing."}]
    while 1:
        query = input('[Query]: ')
        if query.strip() == 'exit' or query.strip() == 'quit':
            break
        res, total_tokens = query_with_history(msg_with_hist, query, llm_model, True)
        print('[%d tokens] [Response]: %s'%(total_tokens, res))