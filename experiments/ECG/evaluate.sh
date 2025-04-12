#!/bin/bash

# Timeout for strace
timeout_seconds=20
log_file="evaluate_vm.log"

echo "[Evaluation] Run command: $0 $@" >> $log_file

# Rewriting C programs (removing gcc-related lines)
ck_rewrite_prog() {
    local dir=$1
    local cnt=0
    for fpath in "$dir"/*; do
        if [[ ! -f "$fpath" ]]; then continue; fi
        prog_str=$(cat "$fpath")
        if [[ "$prog_str" == *"gcc"* ]]; then
            prog_lines=$(echo "$prog_str" | tr '\n' '\n')
            new_prog_str=""
            while IFS= read -r line; do
                next_line=$(echo "$prog_lines" | sed -n '$((i+1))p')
                if [[ "$line" == "}" && "$next_line" == *"gcc"* ]]; then
                    new_prog_str+="$line"
                    break
                fi
                new_prog_str+="$line"
            done <<< "$prog_lines"
            echo "$new_prog_str" > "$fpath"
            ((cnt++))
        fi
    done
    echo "Rewrite success: $cnt/$(ls "$dir" | wc -l)" >> $log_file
}

# Rename files to .c extension
rename2c() {
    local dir=$1
    local cnt=0
    for fpath in "$dir"/*; do
        if [[ ! -f "$fpath" || "$fpath" == *.c ]]; then continue; fi
        mv "$fpath" "$fpath.c"
        ((cnt++))
    done
    echo "Rename success: $cnt/$(ls "$dir" | wc -l)" >> $log_file
}

# Compile C files
compile_c() {
    local dir=$1
    local compiled_dir="${dir}_compiled"
    local cnt=0
    local total=0
    
    mkdir -p "$compiled_dir"
    echo "Start to compile..."
    rm /tmp/compile_error.log
    
    for c_file in "$dir"/*.c; do
        if [[ ! -f "$c_file" ]]; then continue; fi
        ((total++))
        
        local binary_name=$(basename "$c_file" .c)
        local binary_path="$compiled_dir/$binary_name"
        
        if gcc "$c_file" -o "$binary_path" 2>>/tmp/compile_error.log; then
            ((cnt++))
        else
            echo "Compilation failed: $c_file"
            cat /tmp/compile_error.log
        fi
    done
    
    echo "Compile success: $cnt/$total" >> $log_file
    
    if [[ $cnt -eq 0 ]]; then
        return 1
    fi
    return 0
}

# Trace binary with strace
trace_binary() {
    local dir=$1
    local trace_dir="${dir}_trace"
    local cnt=0
    local total=0
    
    mkdir -p "$trace_dir"
    echo "Start to strace..."
    
    for binary_file in "$dir"/*; do
        if [[ ! -f "$binary_file" ]]; then continue; fi
        ((total++))
        
        local binary_name=$(basename "$binary_file")
        local trace_file="$trace_dir/$binary_name.trace"
        
        if timeout $timeout_seconds strace -o "$trace_file" -s 65500 -v -xx -f -Xraw "$binary_file"; then
            ((cnt++))
        else
            echo "Execution failed: $binary_file"
        fi
    done
    
    echo "Strace success: $cnt/$total" >> $log_file
    
    if [[ $cnt -eq 0 ]]; then
        return 1
    fi
    return 0
}

# Convert trace files to syzkaller programs
trace2syz_convert() {
    local trace_dir=$1
    local syz_dir="${trace_dir}_syz"
    local cnt=0
    local total=0
    
    # 创建输出目录
    mkdir -p "$syz_dir"
    echo "Start to convert traces to syzkaller programs..."
    
    # 逐个处理trace文件
    for trace_file in "$trace_dir"/*; do
        if [[ ! -f "$trace_file" ]]; then continue; fi
        ((total++))
        
        echo "Converting: $(basename "$trace_file")"
        
        # 执行转换
        if ./trace2syz -file "$trace_file" -deserialize "$syz_dir" 2>/dev/null; then
            ((cnt++))
        else
            echo "Failed: $(basename "$trace_file")"
        fi
    done
    
    echo "Trace2syz success: $cnt/$total" >> $log_file
    
    if [[ $cnt -eq 0 ]]; then
        return 1
    fi
    return 0
}

# Refine trace files by removing leading / in quoted paths
refine_traces() {
    local trace_dir=$1
    local refined_dir="${trace_dir}_ref"
    local cnt=0
    local total=0
    
    # 创建输出目录
    mkdir -p "$refined_dir"
    echo "Start to refine trace files..."
    
    # 处理每个trace文件
    for trace_file in "$trace_dir"/*; do
        if [[ ! -f "$trace_file" ]]; then continue; fi
        ((total++))
        
        local filename=$(basename "$trace_file")
        local output_file="$refined_dir/$filename"
        
        # 使用sed处理文件：只删除引号内开头的\x2f
        sed 's/"\\x2f\([^"]*\)"/"\1"/g' "$trace_file" > "$output_file"
        
        if [[ $? -eq 0 ]]; then
            ((cnt++))
        else
            echo "Failed to process: $trace_file"
        fi
    done
    
    echo "Refine success: $cnt/$total" >> $log_file
    
    return 0
}

# Check if generated traces contain target syscalls
check_syscalls() {
    local syz_dir=$1
    local json_file=$2
    local syz_contain_dir="${syz_dir}_contain"
    local cnt=0
    local total=0

    mkdir -p "$syz_contain_dir"
    if [[ ! -f "$json_file" ]]; then
        echo "Error: JSON file not found: $json_file"
        return 1
    fi
    
    echo "Start checking syscalls in traces..."
    echo "Using JSON file: $json_file"
    
    # 读取generation_history.json
    while IFS= read -r line; do        
        # 匹配系统调用名称行
        if [[ "$line" =~ \"([^\"]+)\"\:\ \[ ]]; then
            syscall="${BASH_REMATCH[1]}"
        # 匹配哈希值行
        elif [[ "$line" =~ \"([a-f0-9]+)\" ]]; then
            hash="${BASH_REMATCH[1]}"
            if [[ -n "$syscall" ]]; then
                local trace_file="$syz_dir/${hash}.trace0"
                echo "Check for syscall: $syscall in $trace_file"
                
                # 检查文件是否存在且包含目标syscall
                if [[ -f "$trace_file" ]]; then
                    if grep -q "$syscall" "$trace_file"; then
                        ((cnt++))
                        ((total++))
                        cp "$trace_file" "$syz_contain_dir"
                    else
                        echo "Failed: $trace_file does not contain $syscall"
                        ((total++))
                    fi
                else
                    echo "Warning: $trace_file not found"
                fi
                syscall=""  # 重置系统调用变量
            fi
        fi
    done < "$json_file"
    
    echo "Syscall check success: $cnt/$total" >> $log_file
    
    if [[ $cnt -eq 0 ]]; then
        return 1
    fi
    return 0
}

# Run all steps in sequence
run_all() {
    local c_dir=$1
    local json_file=$2
    local success=true
    
    touch $log_file && rm $log_file
    echo "[Start full evaluation process]" >> $log_file
    
    # Step 1: Rename files to .c
    echo "Step 1: Renaming files to .c extension..."
    if ! rename2c "$c_dir"; then
        echo "Warning: rename2c step had issues"
        success=false
    fi
    
    # Step 2: Compile C files
    echo "Step 2: Compiling C files..."
    if ! compile_c "$c_dir"; then
        echo "Warning: compile step had issues"
        success=false
    fi
    
    # Step 3: Run strace
    echo "Step 3: Running strace..."
    if ! trace_binary "${c_dir}_compiled"; then
        echo "Warning: strace step had issues"
        success=false
    fi
    
    # Step 4: Refine traces
    echo "Step 4: Refining traces..."
    if ! refine_traces "${c_dir}_compiled_trace"; then
        echo "Warning: refine step had issues"
        success=false
    fi
    
    # Step 5: Convert to syzkaller programs
    echo "Step 5: Converting to syzkaller programs..."
    if ! trace2syz_convert "${c_dir}_compiled_trace_ref"; then
        echo "Warning: trace2syz step had issues"
        success=false
    fi
    
    # Step 6: Check syscalls
    echo "Step 6: Checking syscalls..."
    if ! check_syscalls "${c_dir}_compiled_trace_ref_syz" "$json_file"; then
        echo "Warning: syscall check step had issues"
        success=false
    fi
    
    echo "[Full evaluation process completed]" >> $log_file
    
    if $success; then
        echo "All steps completed successfully"
        return 0
    else
        echo "Some steps had issues, check the log file for details"
        return 1
    fi
}

# Main
if [[ "$1" == "rewrite" ]]; then
    ck_rewrite_prog "$2"
elif [[ "$1" == "rename" ]]; then
    rename2c "$2"
elif [[ "$1" == "compile" ]]; then
    compile_c "$2"
elif [[ "$1" == "strace" ]]; then
    trace_binary "$2"
elif [[ "$1" == "refine" ]]; then
    refine_traces "$2"
elif [[ "$1" == "trace2syz" ]]; then
    trace2syz_convert "$2"
elif [[ "$1" == "checksyscall" ]]; then
    if [[ $# -lt 3 ]]; then
        echo "Usage: $0 checksyscall <trace_dir_syz> <json_file>"
        exit 1
    fi
    check_syscalls "$2" "$3"
elif [[ "$1" == "all" ]]; then
    if [[ $# -lt 3 ]]; then
        echo "Usage: $0 all <c_programs_dir> <json_file>"
        exit 1
    fi
    run_all "$2" "$3"
fi

echo "[Evaluation finished in VM]" >> $log_file