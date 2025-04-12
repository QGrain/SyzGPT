# Fine-tune and Serve CodeLlama-syz

We will also release our fine-tuned model "CodeLlama-syz-7b" on Huggingface later.

## 1 Instruct Fine-Tune

### 1.1 Environments

- Install the dependencies:

```bash
pip install -r requirements.txt
```
- Configure **accelerator** to use specific GPUs: Please refer to Internet for guidance.
- Configure **wandb** according to your need: Please refer to Internet for guidance.
- Download base LLM **CodeLlama-7b-Instruct-hf**.

### 1.2 Train

We have prepared a small dataset (8k train and 3k eval) at [./dataset](./dataset/).

You can also build your own dataset by transforming the contextually effective Syz-programs and the corresponding prompts in format of the shown jsonl.

Then we can luanch the traning by `python` or `launch` (if accelerator is configured) .

```bash
python/accelerate launch instruct_tuning.py \
    --model_path /path/to/CodeLlama \
    --max_step 16000 \
    --batch_size 1 \
    --seed N \
    --output_dir ./output/CodeLlama-7b-Instruct-syz-2epochs \
    # --enable_wandb
    # ... more params please refer to -h or src code
```

## 2 Serve Model

We recommend to use `Ollama` or `FastChat` to deploy the tuned model.

Take `FastChat` as an example:

1. Install the dependencies according to [Install FastChat](https://github.com/lm-sys/FastChat?tab=readme-ov-file#install).
2. Launch the controller

```bash
python3 -m fastchat.serve.controller
```

3. Load model

```bash
# recommend to use vllm optimization
CUDA_VISIBLE_DEVICES=X python3 -m fastchat.serve.vllm_worker --gpu_memory_utilization 0.6 --model-path output/CodeLlama-7b-Instruct-syz-2epochs
```

4. Launch API

```bash
# support openai API
python3 -m fastchat.serve.openai_api_server --host 0.0.0.0 --port 38950
```


**Make sure the machine serving this model is accessible to SyzGPT-fuzzer.**