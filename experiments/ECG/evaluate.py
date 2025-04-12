import os
import argparse
from syzqemuctl import ImageManager, VM
from time import sleep, time


def prepare_vm(image_name):
    manager = ImageManager("/root/images-auto")
    manager.create(image_name)
    vm = VM(os.path.join("/root/images-auto", image_name))
    vm.start(kernel="/g.linux/deadline/code/objs/linux-stable-6.6.12")
    return vm


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Evaluate the generation of ECG")
    parser.add_argument("-i", "--image_name", required=True, type=str, help="image name")
    parser.add_argument("-d", "--dir", required=True, type=str, help="directory to the LLM generated results")
    parser.add_argument("-b", "--trace2syz_bin", default="./trace2syz", type=str, help="path to trace2syz binary")
    args = parser.parse_args()
    
    assert os.path.exists(args.trace2syz_bin), f"trace2syz binary not found at {args.trace2syz_bin}"
    
    start_time = time()
    f_log = open(os.path.join(args.dir, "evaluate_local.log"), "w", encoding="utf-8")
    
    vm = prepare_vm(args.image_name)
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
