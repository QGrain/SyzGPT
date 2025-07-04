###############################
# YOU CAN EDIT THE FOLLOWINGS #
###############################

# Copy config.py to private_config.py and EDIT API_KEY in private_config.py
API_KEY = "sk-*** YOUR API KEY ***"

USE_PROXY = False
if USE_PROXY:
    proxies = {
        "http":  "http://localhost:7890",
        "https": "http://localhost:7890",
    }
else:
    proxies = {
        "http":  None,
        "https": None,
    }

# Change the model you want to use here, which would be overwritten by the command line argument -M/--model.
# If you specify a new model, please make sure to add it to the MAX_TOKEN dict below.
# In our experiments, we prefer to use "gpt-3.5-turbo-16k-0613", which is unfortunately deprecated by OpenAI so far.
LLM_MODEL = "gpt-3.5-turbo-16k-0613"


##############################
# DO NOT EDIT THE FOLLOWINGS #
##############################

OUT_DIR = './corpus'
LOG_DIR = './log'


RETRY_WAIT = 60

# We recommend to set max_token to 2560 for most models with context window <= 16k, and set 4096 for models with context window >= 32k.
# Well, this is due the ancient era of LLMs, where most of the models do not have a great context window.
MAX_TOKEN = {
    "gpt-3.5-turbo": 2048,
    "gpt-3.5-turbo-1106": 2560,
    "gpt-3.5-turbo-0125": 2560,
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