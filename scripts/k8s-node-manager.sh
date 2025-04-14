#!/bin/bash

# 检查 dialog 是否安装
if ! command -v dialog &> /dev/null; then
    echo "请先安装 dialog: brew install dialog"
    exit 1
fi

# 检查必要工具
check_requirements() {
    if ! command -v minikube &> /dev/null; then
        dialog --title "错误" --msgbox "未安装 minikube，请先安装 minikube" 8 40
        exit 1
    fi
    if ! command -v kubectl &> /dev/null; then
        dialog --title "错误" --msgbox "未安装 kubectl，请先安装 kubectl" 8 40
        exit 1
    fi
}

# 显示结果
show_result() {
    local title="$1"
    local command="$2"
    result=$($command)
    dialog --title "$title" --msgbox "$result" 20 80
}

# 获取用户输入
get_input() {
    local title="$1"
    local text="$2"
    dialog --title "$title" --inputbox "$text" 8 40 2>&1 >/dev/tty
}

# 主程序
main() {
    check_requirements
    
    while true; do
        choice=$(dialog --title "Kubernetes 节点管理工具" --menu "请选择操作：" 20 60 11 \
            1 "查看所有节点状态" \
            2 "查看节点详细信息" \
            3 "查看节点资源使用情况" \
            4 "添加新节点" \
            5 "停止 Minikube 集群" \
            6 "启动 Minikube 集群" \
            7 "重置 Minikube 集群" \
            8 "查看节点 taints" \
            9 "添加节点 taint" \
            10 "删除节点 taint" \
            0 "退出" 2>&1 >/dev/tty)

        case $choice in
            1)
                show_result "节点状态" "kubectl get nodes"
                ;;
            2)
                show_result "节点详细信息" "kubectl describe nodes"
                ;;
            3)
                show_result "资源使用情况" "kubectl top nodes"
                ;;
            4)
                dialog --title "添加节点" --infobox "正在添加新的 worker 节点..." 3 40
                minikube node add --worker=true
                show_result "节点添加完成" "kubectl get nodes"
                ;;
            5)
                dialog --title "停止集群" --infobox "正在停止 Minikube 集群..." 3 40
                minikube stop
                ;;
            6)
                dialog --title "启动集群" --infobox "正在启动 Minikube 集群..." 3 40
                minikube start
                ;;
            7)
                if dialog --title "重置集群" --yesno "确定要重置 Minikube 集群吗？" 7 40; then
                    minikube delete
                    minikube start
                fi
                ;;
            8)
                show_result "Taints 信息" "kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints"
                ;;
            9)
                # 获取所有节点名称并构建菜单选项
                node_list=$(kubectl get nodes --no-headers -o custom-columns=NAME:.metadata.name)
                menu_items=""
                index=1
                for node in $node_list; do
                    menu_items="$menu_items $index $node"
                    ((index++))
                done
                
                # 显示节点选择菜单
                node_name=$(dialog --title "选择节点" --menu "请选择要添加 Taint 的节点：" 15 50 5 $menu_items 2>&1 >/dev/tty)
                if [ -n "$node_name" ]; then
                    # 将选择的序号转换为节点名称
                    node_name=$(echo "$node_list" | sed -n "${node_name}p")
                    
                    # 显示当前节点的 Taints
                    current_taints=$(kubectl get nodes $node_name -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints)
                    dialog --title "当前 Taints" --msgbox "$current_taints" 10 70
                    
                    # 获取 taint 信息
                    taint_key=$(get_input "添加 Taint" "请输入 taint key：")
                    [ -n "$taint_key" ] && taint_value=$(get_input "添加 Taint" "请输入 taint value：")
                    [ -n "$taint_value" ] && taint_effect=$(dialog --title "添加 Taint" --menu "请选择 taint effect：" 12 40 3 \
                        "NoSchedule" "不调度新 Pod" \
                        "PreferNoSchedule" "尽量不调度" \
                        "NoExecute" "驱逐现有 Pod" 2>&1 >/dev/tty)
                    [ -n "$taint_effect" ] && kubectl taint nodes $node_name $taint_key=$taint_value:$taint_effect
                fi
                ;;
            10)
                # 获取所有节点名称并构建菜单选项
                node_list=$(kubectl get nodes --no-headers -o custom-columns=NAME:.metadata.name)
                menu_items=""
                index=1
                for node in $node_list; do
                    menu_items="$menu_items $index $node"
                    ((index++))
                done
                
                # 显示节点选择菜单
                node_name=$(dialog --title "选择节点" --menu "请选择要删除 Taint 的节点：" 15 50 5 $menu_items 2>&1 >/dev/tty)
                if [ -n "$node_name" ]; then
                    # 将选择的序号转换为节点名称
                    node_name=$(echo "$node_list" | sed -n "${node_name}p")
                    
                    # 获取该节点的所有 taints 信息
                    taint_info=$(kubectl get node $node_name -o jsonpath='{.spec.taints[*]}{"\n"}')
                    if [ -z "$taint_info" ]; then
                        dialog --title "提示" --msgbox "该节点没有 Taint" 8 40
                        continue
                    fi
                    
                    # 构建 taint 选择菜单
                    menu_items="0 删除所有Taints"
                    index=1
                    
                    # 使用更可靠的方式获取和解析 taints
                    while IFS= read -r taint_key && IFS= read -r taint_value && IFS= read -r taint_effect; do
                        # 移除引号，使用空格分隔
                        menu_items="$menu_items $index ${taint_key}=${taint_value}:${taint_effect}"
                        ((index++))
                    done < <(kubectl get node $node_name -o jsonpath='{range .spec.taints[*]}{.key}{"\n"}{.value}{"\n"}{.effect}{"\n"}{end}')
                    
                    # 显示 taint 选择菜单
                    
                    # 记录操作时间和选择的菜单项
                    log_handler "删除 Taint 菜单选项: $menu_items"
                    taint_choice=$(dialog --title "选择 Taint" --menu "请选择要删除的 Taint：" 15 70 10 $menu_items 2>&1 >/dev/tty)
                    log_handler "用户选择: $taint_choice"
                    
                    if [ -n "$taint_choice" ]; then
                        if [ "$taint_choice" = "0" ]; then
                            # 删除所有 taints
                            for key in $(kubectl get node $node_name -o jsonpath='{range .spec.taints[*]}{.key}{"\n"}{end}'); do
                                kubectl taint nodes $node_name "$key-"
                            done
                            dialog --title "成功" --msgbox "已删除所有 Taints" 8 40
                        else
                            # 删除选中的 taint
                            key=$(kubectl get node $node_name -o jsonpath="{.spec.taints[$(($taint_choice-1))].key}")
                            kubectl taint nodes $node_name "$key-"
                        fi
                        show_result "Taints 信息" "kubectl get nodes $node_name -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints"
                    fi
                fi
                ;;
            11)
                old_name=$(get_input "修改节点名称" "请输入当前节点名称：")
                [ -n "$old_name" ] && new_name=$(get_input "修改节点名称" "请输入新的节点名称：")
                [ -n "$new_name" ] && kubectl get node $old_name -o yaml | sed "s/name: $old_name/name: $new_name/" | kubectl replace --force -f -
                ;;
            0|"")
                clear
                exit 0
                ;;
        esac
    done
}

# 日志处理函数
log_handler() {
    local message="$1"
    local log_name="${2:-operations}"  # 如果未指定日志名称，默认使用 operations
    local log_dir="./logs"
    local log_file="$log_dir/${log_name}.log"
    
    # 确保日志目录存在
    mkdir -p "$log_dir"
    
    # 写入日志
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$log_file"
}


main