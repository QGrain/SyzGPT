#!/bin/bash
# Install old version llvm-project from source. Two reasons why use this script:
# 1. llvm-project before 9.0.1 does not have a tarball of llvm-project. We need to download them seperately.
# 2. Older llvm-project (before 9.0.1?) uses some features which would be changed or deprecated in C++17. So we'd better use gcc-5 to compile llvm.

set -e

cwd=`pwd`
ver=$1
packages=(llvm cfe compiler-rt libcxx libcxxabi lld clang-tools-extra)
base_url=https://releases.llvm.org/$ver

src_dir=llvm-project-$ver.src
install_dir=llvm-project-$ver.install

mkdir $src_dir $install_dir

# download and extract
pushd $src_dir
for pack in ${packages[@]}
do
        wget $base_url/$pack-$ver.src.tar.xz
        tar xvJf $pack-$ver.src.tar.xz
done
echo -e "\ndownload and extract finish"

mv llvm-$ver.src llvm
mv cfe-$ver.src clang
mv compiler-rt-$ver.src compiler-rt
mv libcxx-$ver.src libcxx
mv libcxxabi-$ver.src libcxxabi
mv lld-$ver.src lld
mv clang-tools-extra-$ver.src clang-tools-extra


# build in $src_dir
mkdir build
cd build

cmake -G Ninja\
                -DCMAKE_BUILD_TYPE=Release \
                # -DLLVM_ENABLE_PROJECTS="clang;lld;compiler-rt" \
                -DLLVM_TARGETS_TO_BUILD="X86" \
                -DCMAKE_INSTALL_PREFIX=$cwd/$install_dir \
                -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi" ../llvm

# cmake -G Ninja -DLIBCXX_ENABLE_SHARED=OFF -DLIBCXX_ENABLE_STATIC_ABI_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD="X86" -DLLVM_BINUTILS_INCDIR=/usr/include ../llvm

echo -e "\ncmake finish\n"
ninja -j16
echo -e "\nninja finish, return value: $?"
echo -e "\nplease: cd $cwd$src_dir/build && ninja install"