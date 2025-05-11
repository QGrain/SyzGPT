#!/bin/bash

set -e

print_help()
{
    echo -e "Usage: ./build_llvm-project.sh LLVM_VERSION [-jN]\n"
    echo -e "[Notice] LLVM_VERSION's format is X.Y.Z, *-rcN versions are not supported\n"
    exit 1
}


get_url()
{
    OLD_IFS=$IFS
    IFS="."
    arr=($1)
    IFS=$OLD_IFS

    ver_val=0
    for i in $(seq 0 2)
    do
        ver_val=`echo "$ver_val * 10 + ${arr[$i]}" | bc`
    done

    new_ver=1101
    old_ver=901
    if [[ $ver_val -ge $new_ver ]]; then
        echo "https://github.com/llvm/llvm-project/releases/download/llvmorg-$1/llvm-project-$1.src.tar.xz"
    elif [[ $ver_val -ge $old_ver ]]; then
        echo "https://github.com/llvm/llvm-project/releases/download/llvmorg-$1/llvm-project-$1.tar.xz"
    else
    	echo "Old version < 9.0.1, not supported (TODO). Exit."
    	exit 1
    fi
}


# Parse command line arguments
while getopts "j:" opt; do
    case $opt in
        j)
            thread_count="$OPTARG"
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            print_help
            ;;
    esac
done
shift "$((OPTIND-1))"  # Shift off the processed options and arguments


cwd=`pwd`
version=$1 # like 13.0.1, 17.0.6

if [[ ! $version ]]; then
    echo -e "version is NULL\n"
    print_help
fi

# dependencies
sudo apt update
sudo apt install -y cmake ninja-build libedit-dev python3-dev swig

# download source
INSTALL_DIR=llvm-project-$version.install
URL=`get_url $version`
SRC_DIR=$(basename $URL .tar.xz)

if [[ ! -e $SRC_DIR.tar.xz ]]; then
	wget $URL
fi

if [[ ! -d $SRC_DIR ]]; then
	tar xvJf $SRC_DIR.tar.xz
fi

if [[ ! -d $INSTALL_DIR ]]; then
	mkdir $INSTALL_DIR
	mkdir -p $SRC_DIR/build
fi

cd $SRC_DIR/build

# Notice, compiler-rt has trouble with old ver of llvm
cmake -G Ninja\
                -DCMAKE_BUILD_TYPE="Release" \
                -DLLVM_ENABLE_PROJECTS="clang;lld;compiler-rt" \
                -DLLVM_TARGETS_TO_BUILD="X86" \
                -DLLVM_INSTALL_UTILS=ON \
                -DCMAKE_INSTALL_PREFIX=$cwd/$INSTALL_DIR \
                -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi" ../llvm

echo -e "\ncmake finish\n"

# Use -jN if provided, otherwise default to hafl of $(nproc)
if [[ ! -z "$thread_count" ]]; then
    ninja -j$thread_count
else
    ninja -j$(($(nproc)/2))
fi

echo -e "\nninja finish, return value: $?"
cd $cwd/$SRC_DIR/build && ninja install
echo -e "\nninja install finish, return value: $?"
echo "export PATH=$cwd/$INSTALL_DIR/bin:\$PATH" >> ~/.bashrc
echo -e "\nadd $cwd/$INSTALL_DIR/bin to PATH in ~/.bashrc"

# Clean up unused files
cd $cwd
rm -rf $SRC_DIR && rm $SRC_DIR.tar.xz
echo -e "\nclean up $SRC_DIR and $SRC_DIR.tar.xz, everything is done!"