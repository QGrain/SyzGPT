import argparse
import os
import torch
from torch.optim import AdamW
from transformers import get_cosine_schedule_with_warmup
from torch.utils.data import DataLoader
import numpy

from accelerate import Accelerator
from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    set_peft_model_state_dict,
)
from torch.utils.data import IterableDataset, Subset
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    logging,
    set_seed,
)
from transformers import (
    TrainerCallback,
    TrainingArguments,
    TrainerState,
    TrainerControl,
)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_path", type=str, default="/path/to/CodeLlama-7b-Instruct-hf", help="path to LLM to tune"
    )

    parser.add_argument("--input_column_name", type=str, default="question")
    parser.add_argument("--output_column_name", type=str, default="answer")

    parser.add_argument("--seq_length", type=int, default=2048)
    parser.add_argument("--max_steps", type=int, default=8000, help="num of max_steps, specify according to the size of dataset, default 8000")
    parser.add_argument("--batch_size", type=int, default=1, help="num of batch_size, default 1")
    parser.add_argument("--gradient_accumulation_steps", type=int, default=1)
    parser.add_argument("--eos_token_id", type=int, default=2)

    parser.add_argument("--lora_r", type=int, default=8)
    parser.add_argument("--lora_alpha", type=int, default=32) # previous default= 32
    parser.add_argument("--lora_dropout", type=float, default=0.05) #previous_default = 0.05

    parser.add_argument("--learning_rate", type=float, default=5e-6)
    parser.add_argument("--lr_scheduler_type", type=str, default="cosine")
    parser.add_argument("--num_warmup_steps", type=int, default=50)
    parser.add_argument("--weight_decay", type=float, default=0.03)

    parser.add_argument("--local_rank", type=int, default=0)
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument(
        "--no_gradient_checkpointing", action="store_false", default=False
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument(
        "--output_dir", type=str, default="./output/CodeLlama-7b-Instruct-tuned", help="save the results to"
    )
    parser.add_argument("--log_freq", default=10, type=int)
    parser.add_argument("--eval_freq", default=1000, type=int)
    parser.add_argument("--save_freq", default=4000, type=int)
    parser.add_argument("--nosafe_save_freq", default=4000, type=int)
    parser.add_argument("--enable_wandb", action="store_true")

    return parser.parse_args()


def chars_token_ratio(dataset, tokenizer, input_column_name="question", output_column_name="answer", nb_examples=400):
    """
    Estimate the average number of characters per token in the dataset.
    """
    total_characters, total_tokens = 0, 0
    for _, example in tqdm(zip(range(nb_examples), iter(dataset)), total=nb_examples):
        text = prepare_sample_text(example, input_column_name, output_column_name)
        total_characters += len(text)
        if tokenizer.is_fast:
            total_tokens += len(tokenizer(text).tokens())
        else:
            total_tokens += len(tokenizer.tokenize(text))

    return total_characters / total_tokens


def print_trainable_parameters(model):
    """
    Prints the number of trainable parameters in the model.
    """
    trainable_params = 0
    all_param = 0
    for _, param in model.named_parameters():
        all_param += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
    print(
        f"trainable params: {trainable_params} || all params: {all_param} || trainable%: {100 * trainable_params / all_param}"
    )


def prepare_sample_text(
    example, input_column_name="question", output_column_name="answer"
):
    """Prepare the text from a sample of the dataset."""
    text = f"Question: {example[input_column_name]}\n\nAnswer: {example[output_column_name]}"
    return text


class ConstantLengthDataset(IterableDataset):
    """
    Iterable dataset that returns constant length chunks of tokens from stream of text files.
        Args:
            tokenizer (Tokenizer): The processor used for proccessing the data.
            dataset (dataset.Dataset): Dataset with text files.
            infinite (bool): If True the iterator is reset after dataset reaches end else stops.
            seq_length (int): Length of token sequences to return.
            num_of_sequences (int): Number of token sequences to keep in buffer.
            chars_per_token (int): Number of characters per token used to estimate number of tokens in text buffer.
    """

    def __init__(
        self,
        tokenizer,
        dataset,
        infinite=False,
        seq_length=1024,
        num_of_sequences=1024,
        chars_per_token=3.6,
        input_column_name="question",
        output_column_name="answer"
    ):
        self.tokenizer = tokenizer
        self.concat_token_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else args.eos_token_id
        self.dataset = dataset
        self.seq_length = seq_length
        self.infinite = infinite
        self.current_size = 0
        self.max_buffer_size = seq_length * chars_per_token * num_of_sequences
        self.input_column_name = input_column_name
        self.output_column_name = output_column_name

    def __iter__(self):
        iterator = iter(self.dataset)
        more_examples = True
        while more_examples:
            buffer, buffer_len = [], 0
            while True:
                if buffer_len >= self.max_buffer_size:
                    break
                try:
                    buffer.append(prepare_sample_text(next(iterator), self.input_column_name, self.output_column_name))
                    buffer_len += len(buffer[-1])
                except StopIteration:
                    if self.infinite:
                        iterator = iter(self.dataset)
                    else:
                        more_examples = False
                        break
            tokenized_inputs = self.tokenizer(buffer, truncation=False)["input_ids"]
            all_token_ids = []
            for tokenized_input in tokenized_inputs:
                all_token_ids.extend(tokenized_input + [self.concat_token_id])
            for i in range(0, len(all_token_ids), self.seq_length):
                input_ids = all_token_ids[i : i + self.seq_length]
                if len(input_ids) == self.seq_length:
                    self.current_size += 1
                    yield {
                        "input_ids": torch.LongTensor(input_ids),
                        "labels": torch.LongTensor(input_ids),
                    }



def create_datasets(tokenizer, args):
    train_data = load_dataset('json', data_files='./dataset/train_dataset.jsonl', split='train')
    valid_data = load_dataset('json', data_files='./dataset/eval_dataset.jsonl', split='train')
    print(f"Size of the train set: {len(train_data)}. Size of the validation set: {len(valid_data)}")

    chars_per_token = chars_token_ratio(train_data, tokenizer, args.input_column_name, args.output_column_name)
    print(f"The character to token ratio of the dataset is: {chars_per_token:.2f}")

    train_dataset = ConstantLengthDataset(
        tokenizer,
        train_data,
        infinite=True,
        seq_length=args.seq_length,
        chars_per_token=chars_per_token,
        input_column_name=args.input_column_name,
        output_column_name=args.output_column_name
    )
    valid_dataset = ConstantLengthDataset(
        tokenizer,
        valid_data,
        infinite=False,
        seq_length=args.seq_length,
        chars_per_token=chars_per_token,
        input_column_name=args.input_column_name,
        output_column_name=args.output_column_name
    )
    return train_dataset, valid_dataset


def run_training(args, train_data, val_data, tokenizer):
    if args.enable_wandb == True:
        accelerator = Accelerator(log_with="wandb")
        accelerator.init_trackers(
            project_name="fine-tune_codellama_7b_instruct",
            config=vars(args),
            init_kwargs={
                "wandb": {
                    "name": "you_job_title",
                    "mode": "online",
                }
            },
        )
    else:
        accelerator = Accelerator()
    print("Loading the model")

    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        use_cache=args.no_gradient_checkpointing,
        load_in_8bit=True,
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        inference_mode=False,
        fan_in_fan_out=False,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            # "down_proj",
            # "gate_proj",
            # "up_proj",
        ],
    )
    model = get_peft_model(model, lora_config)

    train_dl = DataLoader(
        train_data, batch_size=args.batch_size, num_workers=3, prefetch_factor=2
    )
    test_dl = DataLoader(
        val_data, batch_size=4, num_workers=3, prefetch_factor=2
    )
    optimizer = AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    scheduler = get_cosine_schedule_with_warmup(
        optimizer, args.num_warmup_steps, args.max_steps
    )

    model, train_dl, optimizer, scheduler, test_dl = accelerator.prepare(
        model, train_dl, optimizer, scheduler, test_dl
    )

    prog_bar = tqdm(
        total=args.max_steps, disable=not accelerator.is_local_main_process, position=1
    )
    step = 0
    while True:
        if step >= args.max_steps:
            break

        for batch in train_dl:
            model.train()
            with accelerator.accumulate(model):
                output = model(**batch)
                accelerator.backward(output.loss)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            step += 1
            prog_bar.update(1)
            prog_bar.set_description(
                f"Loss: {output.loss.item():.6f}, LR: {scheduler.get_last_lr()[0]:.6f}"
            )


            if step % args.nosafe_save_freq == 0:
                chpt = os.path.join(args.output_dir, f"checkpoint_nosafe_{step}")
                accelerator.unwrap_model(model).save_pretrained(chpt, safe_serialization=False)
            elif step % args.save_freq == 0:
                chpt = os.path.join(args.output_dir, f"checkpoint_{step}")
                accelerator.unwrap_model(model).save_pretrained(chpt)

            accelerator.log(
                {"loss": output.loss.item(), "LR": scheduler.get_last_lr()[0]}, step=step
            )
            if step >= args.max_steps:
                break

    chpt = os.path.join(args.output_dir, f"checkpoint_{step}")
    accelerator.unwrap_model(model).save_pretrained(chpt)


def main(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    train_dataset, eval_dataset = create_datasets(tokenizer, args)
    run_training(args, train_dataset, eval_dataset, tokenizer)


if __name__ == "__main__":
    args = get_args()
    print(args)
    set_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    logging.set_verbosity_error()

    main(args)