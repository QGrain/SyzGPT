import os
import argparse
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


# python evaluate.py -i /root/images-auto -n image-ecg -k /g.linux/deadline/code/objs/linux-stable-6.6.12 -d /path/to/ecg/outs -b /root/fuzzers/SyzGPT-fuzzer/tools/syz-trace2syz/trace2syz
if __name__ == "__main__":
    parser = argparse.ArgumentParser("Evaluate the generation of ECG")
    parser.add_argument("-i", "--images_home", default="/root/images", type=str, help="path to images home")
    parser.add_argument("-n", "--image_name", required=True, type=str, help="image name")
    parser.add_argument("-k", "--kernel_obj", default="/root/kernels/linux-6.6.12", type=str, help="path to kernel object")
    parser.add_argument("-d", "--dir", required=True, type=str, help="directory to the LLM generated results")
    parser.add_argument("-b", "--trace2syz_bin", default="./trace2syz", type=str, help="path to trace2syz binary")
    args = parser.parse_args()
    
    assert os.path.exists(args.trace2syz_bin), f"trace2syz binary not found at {args.trace2syz_bin}"
    
    start_time = time()
    f_log = open(os.path.join(args.dir, "evaluate_local.log"), "w", encoding="utf-8")
    
    vm = prepare_vm(args.images_home, args.image_name, args.kernel_obj)
    if not vm.is_ready():
        print("VM is not ready, sleep 160 seconds")
        sleep(160)
        if vm.wait_until_ready():
            pass
    print("VM is ready")
    f_log.write(f"[cost: {time() - start_time:.2f}s] VM is ready\n")
    
    prog_dir_name = "generated_c_programs"
    gen_history_name = "generation_history.json"
    eval_script_path = "./evaluate.sh"
    
    with vm:
        vm.execute(f"mkdir -p /root/{args.dir}")
        vm.copy_to_vm(os.path.join(args.dir, prog_dir_name), f"/root/{args.dir}/")
        vm.copy_to_vm(os.path.join(args.dir, gen_history_name), f"/root/{args.dir}/")
        vm.copy_to_vm(eval_script_path, f"/root/")
        vm.copy_to_vm(args.trace2syz_bin, f"/root/")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Copy done\n")
        
        vm.execute("chmod +x /root/evaluate.sh")
        vm.execute("rm /root/evaluate_vm.log")
        # print("Start evaluation, executing all steps")
        # vm.execute(f"/root/evaluate.sh all /root/{args.dir}/{prog_dir_name} /root/{args.dir}/{gen_history_name}")
        # print("All steps done")
        vm.execute(f"/root/evaluate.sh rename /root/{args.dir}/{prog_dir_name}")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Rename done\n")
        vm.execute(f"/root/evaluate.sh compile /root/{args.dir}/{prog_dir_name}")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Compile done\n")
        vm.execute(f"/root/evaluate.sh strace /root/{args.dir}/{prog_dir_name}_compiled")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Strace done\n")
        vm.execute(f"/root/evaluate.sh refine /root/{args.dir}/{prog_dir_name}_compiled_trace")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Refine done\n")
        vm.execute(f"/root/evaluate.sh trace2syz /root/{args.dir}/{prog_dir_name}_compiled_trace_ref")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Trace2syz done\n")
        vm.execute(f"/root/evaluate.sh checksyscall /root/{args.dir}/{prog_dir_name}_compiled_trace_ref_syz /root/{args.dir}/{gen_history_name}")
        f_log.write(f"[cost: {time() - start_time:.2f}s] Checksyscall done\n")

    print(f"Evaluation finished in VM, cost: {time() - start_time:.2f}s")
    f_log.write(f"[cost: {time() - start_time:.2f}s] Evaluation finished in VM\n")
    os.makedirs(os.path.join(args.dir, "evaluation_results"), exist_ok=True)
    with vm:
        vm.copy_from_vm(f"/root/{args.dir}/{prog_dir_name}_compiled", os.path.join(args.dir, "evaluation_results"))
        vm.copy_from_vm(f"/root/{args.dir}/{prog_dir_name}_compiled_trace", os.path.join(args.dir, "evaluation_results"))
        vm.copy_from_vm(f"/root/{args.dir}/{prog_dir_name}_compiled_trace_ref", os.path.join(args.dir, "evaluation_results"))
        vm.copy_from_vm(f"/root/{args.dir}/{prog_dir_name}_compiled_trace_ref_syz", os.path.join(args.dir, "evaluation_results"))
        vm.copy_from_vm(f"/root/{args.dir}/{prog_dir_name}_compiled_trace_ref_syz_contain", os.path.join(args.dir, "evaluation_results"))
        vm.copy_from_vm(f"/root/evaluate_vm.log", os.path.join(args.dir, "evaluation_results"))
    vm.stop()
    
    print(f"Evaluation finished! Copy the evaluation results at {os.path.join(args.dir, 'evaluation_results')}. Cost: {time() - start_time:.2f}s")
    f_log.write(f"[cost: {time() - start_time:.2f}s] Evaluation finished! Copy the evaluation results at {os.path.join(args.dir, 'evaluation_results')}\n")
    f_log.close()
