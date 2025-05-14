import os
import sys
import argparse
import subprocess
from syzqemuctl import global_conf, ImageManager, VM
from time import sleep, time

def prepare_vm(images_home: str, image_name: str, kernel_obj: str) -> VM:
    global_conf.initialize(images_home, force=False)
    manager = ImageManager(images_home)
    manager.initialize(force=False)
    manager.create(image_name)

    vm = VM(os.path.join(images_home, image_name))
    vm.start(kernel=kernel_obj)
    return vm


def stop_vm(images_home: str, image_name: str, kernel_obj: str) -> None:
    vm = VM(os.path.join(images_home, image_name))
    vm.stop(kernel=kernel_obj)


def reverse_prog(file_path: str, out_dir: str = None) -> None:
    with open(file_path, 'r') as file:
        lines = file.readlines()
        reversed_lines = [line.strip() + '\n' for line in lines[::-1]]
    
    if out_dir is None:
        out_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    out_path = os.path.join(out_dir, file_name + '.rev')
    with open(out_path, 'w') as f:
        f.writelines(reversed_lines)


def reverse_progs_to_dir(dir_path: str, out_dir: str = None) -> None:
    if not os.path.isdir(dir_path):
        print(f"Invalid directory path: {dir_path}")
        return
    if out_dir is None:
        out_dir = dir_path
    os.makedirs(out_dir, exist_ok=True)
    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if os.path.isfile(file_path):
            reverse_prog(file_path, out_dir)


def calc_SVR(fuzzer_path: str, workdir: str, target: str = "generated_corpus", log_file: str = "evaluation.log") -> None:
    syz_validator_bin = os.path.join(fuzzer_path, 'bin/syz-validator')
    target_dir = os.path.join(workdir, target)
    cmd = f"{syz_validator_bin} dir {target_dir}"
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
    print(res.stdout)
    for line in res.stdout.split('\n'):
        line = line.strip()
        if 'Syntax Valid Rate' in line:
            with open(log_file, 'a') as f:
                f.write(f"Calculate SVR for {target_dir}:\n")
                f.write(f"{line}\n")


def extract_valid_progs(fuzzer_path: str, workdir: str, target: str = "generated_corpus") -> None:
    syz_validator_bin = os.path.join(fuzzer_path, 'bin/syz-validator')
    target_dir = os.path.join(workdir, target)
    extract_dir = os.path.join(workdir, '%_valid'%target)
    cmd = f"{syz_validator_bin} dir {target_dir} {extract_dir}"
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
    if res.returncode != 0:
        print(f"Failed to extract valid progs to {extract_dir}: {res.stderr}")
        sys.exit(1)


def repair_progs(fuzzer_path: str, workdir: str) -> None:
    syz_repair_bin = os.path.join(fuzzer_path, 'bin/syz-repair')
    prog_dir = os.path.join(workdir, 'generated_corpus')
    repair_dir = os.path.join(workdir, 'generated_corpus_repair')
    cmd = f"{syz_repair_bin} {prog_dir} {repair_dir}"
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
    if res.returncode != 0:
        print(f"Failed to repair progs to {repair_dir}: {res.stderr}")
        sys.exit(1)


def calc_N_L(project_root: str, workdir: str, target: str = "generated_corpus_valid", log_file: str = "evaluation.log") -> None:
    target_dir = os.path.join(workdir, target)
    cmd = f"python {project_root}/analyzer/corpus_analyzer.py analyze -d {target_dir}"
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
    print(res.stdout)
    with open(log_file, 'a') as f:
        f.write(f"Calculate Average Number of Syscalls and Average Program Length for {target_dir}:\n")
        f.write(f"{res.stdout}\n")


def calc_CER(fuzzer_path: str, workdir: str, log_file: str = "evaluate.log") -> None:
    # based on syzqemuctl
    # TBD soon
    pass


def evaluate_all_stages(fuzzer_path: str, workdir: dir, log_file: str = "evaluate.log") -> None:
    # stage 1: calculate SVR for original progs
    calc_SVR(fuzzer_path, workdir, log_file)
    
    # stage 2: calculate average N and L for original progs
    extract_valid_progs(fuzzer_path, workdir, "generated_corpus")
    calc_N_L("/root/SyzGPT", workdir, "generated_corpus_valid", log_file)
    
    # stage 3: repair progs and calculate SVR
    repair_progs(fuzzer_path, workdir)
    calc_SVR(fuzzer_path, workdir, "generated_corpus_repair", log_file)
    
    # stage 4: calculate average N and L for repaired progs
    extract_valid_progs(fuzzer_path, workdir, "generated_corpus_repair")
    calc_N_L("/root/SyzGPT", workdir, "generated_corpus_repair_valid", log_file)
    
    # stage 5: calculate CER for valid repaired progs
    

# python /root/SyzGPT/experiments/performance/evaluate.py -i /root/images -n image-eval -k /root/kernels/linux-6.6.12 -s /root/fuzzers/SyzGPT-fuzzer -w WORKDIR
if __name__ == "__main__":
    parser = argparse.ArgumentParser("Evaluate the generation of SyzGPT")
    parser.add_argument("-i", "--images_home", default="/root/images", type=str, help="path to images home")
    parser.add_argument("-n", "--image_name", required=True, type=str, help="image name")
    parser.add_argument("-k", "--kernel_obj", default="/root/kernels/linux-6.6.12", type=str, help="path to kernel object")
    parser.add_argument("-s", "--fuzzer", required=True, type=str, help="path to SyzGPT-fuzzer")
    parser.add_argument("-w", "--workdir", required=True, type=str, help="workdir of the LLM generated results")
    args = parser.parse_args()
    
    
    prepare_vm(args.images_home, args.image_name, args.kernel_obj)
    evaluate_all_stages(args.fuzzer, args.workdir, "evaluate.log")
    stop_vm(args.images_home, args.image_name, args.kernel_obj)