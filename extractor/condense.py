import os
import sys
sys.path.append('..')
import openai
import re
import json
from loguru import logger
from time import sleep
from generator.utils import *
from extractor.extractor_prompts import *
try:
    from private_config import *
except ImportError:
    from config import *

source_dir = '../crawler/man_docs/'
target_dir = '../crawler/condensed_man_docs/'
openai.api_key = API_KEY
openai.proxy = proxies['http']

def send_messages(messages, model='gpt-3.5-turbo-16k-0613', dumb=True, temperature=0.2):
    response = openai.ChatCompletion.create(
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


def query_with_history(messages, query, dumb=True):
    sleep(3)
    max_token = MAX_TOKEN[LLM_MODEL]
    messages.append({"role": "user", "content": query})
    if dumb == False:
        print('[Query]:\n%s'%query)
    try:
        response, total_tokens = send_messages(messages, LLM_MODEL, dumb)
    except openai.error.InvalidRequestError as e:
        logger.exception('Exception occured: %s'%e)
        if 'Please reduce the length of the messages or completion' in str(e):
            match_obj = re.search(r'However, you requested (\d+) tokens', str(e))
            req_tokens = int(match_obj.group(1))
            clip_msg(messages, req_tokens-max_token+SECURE_CLIP)
            sleep(30)
            response, total_tokens = send_messages(messages, LLM_MODEL, dumb)
    except (openai.error.RateLimitError, openai.error.Timeout, openai.error.APIConnectionError) as e:
        sleep(RETRY_WAIT)
        response, total_tokens = send_messages(messages, LLM_MODEL, dumb)
    if dumb == False:
        print('[Response]:\n%s'%response)
    messages.append({"role": "assistant", "content": response})
    return response, total_tokens

def condense_text(text, dumb=False):
    msg_with_hist = [{"role": "system", "content": SYSTEM_PROMPT_CONDENSE}]

    query = 'According to the demand of how to condense text, provide the condensed text of following Linux manual page: "%s"'%text
    simp_result, _ = query_with_history(msg_with_hist, query, LLM_MODEL, dumb)

    return simp_result

for root, dirs, files in os.walk(source_dir):
    for file in files:
        source_file = os.path.join(root, file)
        target_file = os.path.join(target_dir, file)

        with open(source_file, "r", encoding="utf-8") as source:
            # content = source.read()
            syscall_info = json.load(source)

            if "DESCRIPTION" in syscall_info:
                simplified_description = condense_text(syscall_info["DESCRIPTION"], False)
                syscall_info["DESCRIPTION"] = simplified_description
            if "NOTES" in syscall_info:
                simplified_notes = condense_text(syscall_info["NOTES"], False)
                syscall_info["NOTES"] = simplified_notes

        os.makedirs(os.path.dirname(target_file), exist_ok=True)

        with open(target_file, 'w', encoding="utf-8") as target:
            # target.write(syscall_synopsis+syscall_description+syscall_notes)
            json.dump(syscall_info, target, indent=4)

print("one-time condense man docs done.")
