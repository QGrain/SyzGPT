import os
import sys
import subprocess
import argparse

def print_help():
    print("Usage: ./imgmgr.py OPERATION [ARGS...]\n")
    print("Supported OPERATION:\n")
    print("\tcreate:\tcreate a new image directory. ARG1: IMAGE_NAME, [ARG2: /PATH/TO/create-image.sh]\n")
    print("\ttest:\ttest a specified kernel in qemu. ARG1: IMAGE_DIR, ARG2: KERNEL_PATH, ARG3: SSH_PORT\n")
    print("\tdebug:\tscp files to qemu vm and syz-execprog to debug the kernel. ARG1: SCP_FILES, ARG2: IMAGE_DIR\n")

def create(image_name, create_script=None):
    try:
        # Create the image directory
        os.makedirs(image_name, exist_ok=True)

        # Copy the create-image.sh script if provided
        if create_script:
            shutil.copy(create_script, os.path.join(image_name, 'create-image.sh'))
        else:
            # Download create-image.sh if not provided
            create_image_url = "https://raw.githubusercontent.com/google/syzkaller/749afb64a55dba8e4a50d96bc287ae06346b4244/tools/create-image.sh"
            subprocess.run(["wget", create_image_url, "-O", os.path.join(image_name, 'create-image.sh')])

        # Change permission of create-image.sh
        create_script_path = os.path.join(image_name, 'create-image.sh')
        os.chmod(create_script_path, 0o755)

        # Modify create-image.sh if needed
        with open(create_script_path, 'r') as create_script_file:
            create_script_content = create_script_file.read()
            create_script_content = create_script_content.replace("http://deb.debian.org/debian-ports", "https://mirrors.tuna.tsinghua.edu.cn/debian/")
        with open(create_script_path, 'w') as create_script_file:
            create_script_file.write(create_script_content)

        # Start the image creation process in a screen session
        subprocess.run(["screen", "-dmS", "imgmgr_create"])
        subprocess.run(["screen", "-S", "imgmgr_create", "-X", "stuff", "clear\n"])
        subprocess.run(["screen", "-S", "imgmgr_create", "-X", "stuff", f"cd {image_name} && ./create-image.sh && exit\n"])

        print(f"Creating image at {image_name} in imgmgr_create screen...")
    except Exception as e:
        print(f"Error during image creation: {e}")

def test(image_dir, kernel_path, ssh_port):
    # Implement test functionality here
    pass

def debug(image_dir, scp_files):
    # Implement debug functionality here
    pass

def main():
    parser = argparse.ArgumentParser(description='Image Manager for Syzkaller Fuzzing')
    parser.add_argument('operation', choices=['create', 'test', 'debug'], help='Operation to perform')
    parser.add_argument('args', nargs='*', help='Arguments for the operation')

    args = parser.parse_args()

    if args.operation == 'create':
        if len(args.args) < 1:
            print("Missing arguments for 'create' operation.")
            return
        image_name = args.args[0]
        create_script = args.args[1] if len(args.args) > 1 else None
        create(image_name, create_script)
    elif args.operation == 'test':
        if len(args.args) < 3:
            print("Missing arguments for 'test' operation.")
            return
        image_dir = args.args[0]
        kernel_path = args.args[1]
        ssh_port = args.args[2]
        test(image_dir, kernel_path, ssh_port)
    elif args.operation == 'debug':
        if len(args.args) < 2:
            print("Missing arguments for 'debug' operation.")
            return
        image_dir = args.args[0]
        scp_files = args.args[1]
        debug(image_dir, scp_files)
    else:
        print("Invalid operation. Use 'create', 'test', or 'debug'.")

if __name__ == '__main__':
    main()
