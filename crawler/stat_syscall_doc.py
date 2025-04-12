import os, json
import tiktoken


def count_tokens_for_model(string, model_name):
    '''Return the number of tokens in a text string, passing GPT model name'''
    enc = tiktoken.encoding_for_model(model_name)
    return len(enc.encode(string))


def count_tokens_for_enc(string, encoding_name):
    '''Return the number of tokens in a text string, passing encoding name'''
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(string))


def count_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    '''Return the number of tokens used by a list of messages.'''
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return count_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return count_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def stat_man_doc():
    super_long = []
    # Change the following params for more test
    threshold = 6000
    section_target = ['NAME', 'SYNOPSIS', 'DESCRIPTION', 'RETURN VALUE']

    with open('man_docs/all_syscall_doc.json', 'r', encoding='utf-8') as f:
        d = json.load(f)

    max_tok = 0
    max_doc_fn = ''
    for i, call in enumerate(d):
        try:
            total_str = ''
            total_tok = 0
            for section in section_target:
                try:
                    s = d[call][section]
                    total_str += s
                    total_tok += count_tokens_for_model(s, 'gpt-3.5-turbo-0613')
                except:
                    pass
            print('[%d] %s: len(total_str)=%d, num_tokens=%d'%(i+1, call, len(total_str), total_tok))
            if total_tok > max_tok:
                max_tok = total_tok
                max_doc_fn = call
            if total_tok >= threshold:
                super_long.append((call, total_tok))
        except:
            print('[Exception][%d] %s, '%(i+1, call), d[call].keys())


    print('\nThere are %d super long man documentations out of the threshold %d.'%(len(super_long), threshold))
    for i in super_long:
        print('%s, num_tokens=%d'%(i[0], i[1]))
    print('max doc: %s, num_tokens=%d'%(max_doc_fn, max_tok))


def stat_syzlang_doc():
    super_long = []
    # Change the following params for more test
    threshold = 7000
    
    syzlang_doc_dir = '/root/fuzzers/syzkaller/sys/linux'
    i = 0
    max_tok = 0
    max_doc_fn = ''
    for fn in os.listdir(syzlang_doc_dir):
        if fn[-4:] == '.txt':
            i += 1
            doc_path = os.path.join(syzlang_doc_dir, fn)
            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_str = f.read()
            doc_tok = count_tokens_for_model(doc_str, 'gpt-3.5-turbo-0613')
            if doc_tok > max_tok:
                max_tok = doc_tok
                max_doc_fn = fn
            print('[%d] %s: len(doc_str)=%d, num_tokens=%d'%(i, fn, len(doc_str), doc_tok))
            if doc_tok >= threshold:
                super_long.append((fn, doc_tok))
    
    print('\nThere are %d super long syzlang documentations out of the threshold %d.'%(len(super_long), threshold))
    for i in super_long:
        print('%s, num_tokens=%d'%(i[0], i[1]))
    print('max doc: %s, num_tokens=%d'%(max_doc_fn, max_tok))


if __name__ == '__main__':
    stat_man_doc()
    print('------------------------------------------')
    stat_syzlang_doc()