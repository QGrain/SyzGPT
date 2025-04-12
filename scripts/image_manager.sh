#!/bin/bash

set -e

print_help()
{
    echo -e "Usage: ./image_manager.sh OPERATION [ARGS...]\n"
    echo -e "Supported OPERATION:\n"
    echo -e "\tcreate:\tcreate a new image directory. ARG1: IMAGE_NAME, [ARG2: /PATH/TO/create-image.sh]\n"
    echo -e "\ttest:\ttest a specified kernel in qemu. ARG1: IMAGE_DIR, ARG2: KERNEL_PATH, ARG3: SSH_PORT\n"
    echo -e "\tdebug:\tscp files to qemu vm and syz-execprog to debug the kernel. ARG1: SCP_FILES, ARG2: IMAGE_DIR\n"
    exit 0
}

create()
{
    # $1 == IMAGE_NAME, like /path/to/image-test
    # $2 (optional)
    mkdir -p $1
    dn=`dirname $1`
    if [[ $3 ]]; then
        cp $3 $dn/create-image.sh
    else
        # wget the create-image to $1/create-image.sh
        get_create_image_sh "https://raw.githubusercontent.com/google/syzkaller/749afb64a55dba8e4a50d96bc287ae06346b4244/tools/create-image.sh" $dn
    fi
    cd $dn
    chmod create-image.sh
    sed -i 's/http:\/\/deb.debian.org\/debian-ports/https:\/\/mirrors.tuna.tsinghua.edu.cn\/debian\//g' create-image.sh
    screen -dmS imgmgr_create
    screen -S imgmgr_create -X stuff $'clear\n'
    screen -S imgmgr_create -X stuff $'cd $1 && ./create-image.sh && exit\n'
    echo -e "creating image at $dn in imgmgr_create screen..."

    # wait for the creation done
    # or when ./create-image successfully finished, execute exit to quit the screen and tell the user that it's finished
}

test()
{
    # $1 KERNEL_PATH
    # $2 IMAGE_DIR
    # $3 SSH_PORT


    # write the boot_test.sh to $2/boot_test.sh
    # qemu-system-x86_64 \
    # -kernel $1 \
    # -append "console=ttyS0 root=/dev/sda debug earlyprintk=serial slub_debug=QUZ"\
    # -hda ./bullseye.img \
    # -net user,hostfwd=tcp::$3-:22 -net nic   \
    # -enable-kvm \
    # -nographic \
    # -m 2560M \
    # -smp 2 \
    # -pidfile vm.pid \
    # 2>&1 | tee vm.log
    cd $2
    chmod u+x boot_test.sh
    screen -dmS imgmgr_test
    screen -S imgmgr_test -X stuff $'clear\n'
    screen -S imgmgr_test -X stuff $'./boot_test.sh\n'
    echo -e "booting image in imgmgr_test screen..."

    # wait for the mounting and initialization finish, wait for the prompt: Login:
    screen -S imgmgr_test -X stuff $'root\n'
    screen -S imgmgr_test -X stuff $'\n'
    screen -S imgmgr_test -X stuff $'clear\n'
    screen -S imgmgr_test -X stuff $'echo VM_IS_ALIVE\n'
    screen -S imgmgr_test -p 0 -X hardcopy /tmp/screen-output
    if cat /tmp/screen-output | grep -q "VM_IS_ALIVE"; then
        echo -e "test: Success!\n"
        screen -S imgmgr_test -X stuff $'poweroff\n'
        # wait for poweroff
    else
        echo -e "test: Fail!\n"
    
    # quit the screen
    screen -S imgmgr_test -X quit
}

debug()
{
    # start a screen named imgmgr_debug and execute ./boot_test.sh
    # cd the IMAGE_DIR
    # scp -P SSH_PORT -i bullseye.id_rsa SCP_FILES root@localhost:~/
    # screen -S imgmgr_debug -X stuff $'syz-execprog program\n'
    # echo -e "debugging in imgmgr_debug screen\n"
}


print_help