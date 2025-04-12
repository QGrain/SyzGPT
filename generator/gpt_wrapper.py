import re
import sys
sys.path.append('..')
import openai
import httpx
from openai import OpenAI
from time import sleep
try:
    from private_config import *
except ImportError:
    from config import *


SECURE_CLIP = 50


def send_messages_new(client, messages, model, dumb=True, temperature=0.5, freq_penalty=0.1):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        frequency_penalty=freq_penalty,
        max_tokens=MAX_TOKEN[model]
    )

    for choice in response.choices:
        if "text" in choice and dumb == False:
            print('[INFO] find "text" in choice, return from send_messges()')
            return choice.text, response.usage.total_tokens

    return response.choices[0].message.content, response.usage.total_tokens


def send_messages(messages, model='gpt-3.5-turbo-16k-0613', dumb=True, temperature=0.5, freq_penalty=0):
    # response = openai.ChatCompletion.create(
    #     model=model,
    #     messages=messages,
    #     temperature=temperature,
    #     max_tokens=MAX_TOKEN[model]
    # )
    # Migrate to openai v1.x
    response = openai.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=MAX_TOKEN[model]
    )

    for choice in response.choices:
        if "text" in choice and dumb == False:
            print('[INFO] find "text" in choice, return from send_messges()')
            return choice.text, response.usage.total_tokens

    return response.choices[0].message.content, response.usage.total_tokens


def query_with_history_new(client, messages, query, model=LLM_MODEL, dumb=True, temperature=0.5, freq_penalty=0, logger=None):
    # sleep(3)
    max_token = MAX_TOKEN[model]
    max_try, try_cnt = 3, 0
    messages.append({"role": "user", "content": query})
    response, total_tokens = '', 0
    if dumb == False:
        print('[Query]:\n%s'%query)
    while try_cnt < max_try:
        try:
            try_cnt += 1
            response, total_tokens = send_messages_new(client, messages, model, dumb, temperature, freq_penalty)
            break
        except openai.BadRequestError as e:
            if 'Please reduce the length of the messages or' in str(e):
                print('[Max Token Exceeded] %s'%e)
                match_obj = re.search(r'However, you requested (\d+) tokens', str(e))
                req_tokens = int(match_obj.group(1))
                clip_msg(messages, req_tokens-max_token+SECURE_CLIP)
                sleep(RETRY_WAIT)
            else:
                print('[Other Exception] %s'%e)
        except (openai.RateLimitError, openai.Timeout, openai.APIConnectionError, openai.APIError) as e:
        # except Exception as e:
            print('[DEBUG] sleep(%d) and retry in query_with_history'%RETRY_WAIT)
            if logger:
                logger.debug('[query_with_history] exception occured, sleep(%d) and retry %d: %s'%(RETRY_WAIT, try_cnt, e))
            sleep(RETRY_WAIT)
            response, total_tokens = send_messages_new(client, messages, model, dumb, temperature, freq_penalty)
        
    if dumb == False:
        print('[Response]:\n%s'%response)
    messages.append({"role": "assistant", "content": response})
    return response, total_tokens


def query_with_history(messages, query, model=LLM_MODEL, dumb=True, temperature=0.5, logger=None):
    # sleep(3)
    max_token = MAX_TOKEN[model]
    max_try, try_cnt = 3, 0
    messages.append({"role": "user", "content": query})
    response, total_tokens = '', 0
    if dumb == False:
        print('[Query]:\n%s'%query)
    while try_cnt < max_try:
        try:
            try_cnt += 1
            response, total_tokens = send_messages(messages, model, dumb, temperature)
            break
        except openai.BadRequestError as e:
            if 'Please reduce the length of the messages or' in str(e):
                print('[Max Token Exceeded] %s'%e)
                match_obj = re.search(r'However, you requested (\d+) tokens', str(e))
                req_tokens = int(match_obj.group(1))
                clip_msg(messages, req_tokens-max_token+SECURE_CLIP)
                sleep(RETRY_WAIT)
            else:
                print('[Other Exception] %s'%e)
        except (openai.RateLimitError, openai.Timeout, openai.APIConnectionError, openai.APIError) as e:
        # except Exception as e:
            print('[DEBUG] sleep(%d) and retry in query_with_history'%RETRY_WAIT)
            if logger:
                logger.debug('[query_with_history] exception occured, sleep(%d) and retry %d: %s'%(RETRY_WAIT, try_cnt, e))
            sleep(RETRY_WAIT)
            response, total_tokens = send_messages(messages, model, dumb, temperature)
        
    if dumb == False:
        print('[Response]:\n%s'%response)
    messages.append({"role": "assistant", "content": response})
    return response, total_tokens


def clip_msg(msg, clip_char_n):
    pop_cnt = 0
    for i in range(len(msg)):
        if len(msg[i-pop_cnt]['content']) > clip_char_n:
            msg[i-pop_cnt]['content'] = msg[i-pop_cnt]['content'][clip_char_n:]
            break
        else:
            clip_char_n -= len(msg[i-pop_cnt]['content'])
            msg.pop(i-pop_cnt)
            pop_cnt += 1
    print('[INFO] clipped %d strs'%clip_char_n)


openai.api_key = API_KEY
openai.proxy = proxies
client = OpenAI(
    api_key=API_KEY, 
    http_client=httpx.Client(proxies=proxies['http'])
)