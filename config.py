###############################
# YOU CAN EDIT THE FOLLOWINGS #
###############################

# EDIT API_KEY in private_config.py
API_KEY = "sk-*** YOUR API KEY ***"

USE_PROXY = True
if USE_PROXY:
    proxies = {
        "http":  "http://localhost:7890",
        "https": "http://localhost:7890",
    }
else:
    proxies = None

LLM_MODEL = "gpt-3.5-turbo-16k-0613"


##############################
# DO NOT EDIT THE FOLLOWINGS #
##############################

OUT_DIR = './corpus'
LOG_DIR = './log'

# TIMEOUT_SECONDS = 30
# MAX_RETRY = 3
RETRY_WAIT = 60

AVAIL_LLM_MODELS = ["gpt-3.5-turbo", "gpt-3.5-turbo-1106", "gpt-3.5-turbo-16k", "gpt-3.5-turbo-16k-0613", 
                    "gpt-4", "gpt-4-0613", "gpt-4-32k", "gpt-4-32k-0613",
                    "claude-3-5-sonnet-20240620"]
MAX_TOKEN = {
    "gpt-3.5-turbo": 2048,
    "gpt-3.5-turbo-1106": 2560,
    "gpt-3.5-turbo-16k": 2560,
    "gpt-3.5-turbo-16k-0613": 2560,
    "gpt-4": 2560,
    "gpt-4-0613": 2560,
    "gpt-4-32k": 4096,
    "gpt-4-32k-0613": 4096,
    "CodeLlama-7b-Instruct-hf": 2560,
    "CodeLlama-7b-Instruct-ft-7kstep": 2560,
    "CodeLlama-7b-Instruct-ft": 2560,
    "CodeLlama-7b-Instruct-syz-2epochs": 2560,
    "CodeLlama-7b-Instruct-syz": 2560,
    "Qwen-7B-Chat": 2560,
    "Llama-2-7b-chat-hf": 2560,
    "vicuna-7b-v1.5-16k": 2560,
    "Meta-Llama-3-8B-Instruct": 2560,
    "claude-3-5-sonnet-20240620": 4096
}