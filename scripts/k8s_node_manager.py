#!/usr/bin/env python3
import sys
import subprocess
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QComboBox, QLineEdit, QMessageBox,
                            QDialog, QFormLayout, QHBoxLayout, QTableWidget, 
                            QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt

class LogHandler:
    def __init__(self, log_dir="./logs"):
        self.log_dir = log_dir
        self.setup_logging()

    def setup_logging(self):
        import os
        os.makedirs(self.log_dir, exist_ok=True)
        logging.basicConfig(
            filename=f"{self.log_dir}/operations.log",
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def log(self, message, log_name="operations"):
        logging.info(message)

class TaintDialog(QDialog):
    def __init__(self, node_name, parent=None):
        super().__init__(parent)
        self.node_name = node_name
        self.setWindowTitle(f"添加 Taint - {node_name}")
        self.setup_ui()

    def get_current_taints(self):
        try:
            cmd = ["kubectl", "get", "nodes", self.node_name, "-o", 
                  "custom-columns=NAME:.metadata.name,TAINTS:.spec.taints"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取 Taints 失败: {str(e)}")
            return ""

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 显示当前 Taints
        current_taints = self.get_current_taints()
        taints_table = QTableWidget()
        self.setup_taints_table(taints_table, current_taints)
        layout.addWidget(QLabel("当前 Taints:"))
        layout.addWidget(taints_table)
        
        # Taint 表单
        form = QFormLayout()
        self.key_input = QLineEdit()
        self.value_input = QLineEdit()
        self.effect_combo = QComboBox()
        self.effect_combo.addItems(["NoSchedule", "PreferNoSchedule", "NoExecute"])
        
        form.addRow("Key:", self.key_input)
        form.addRow("Value:", self.value_input)
        form.addRow("Effect:", self.effect_combo)
        layout.addLayout(form)
        
        # 按钮
        buttons = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        
        self.setLayout(layout)

    def setup_taints_table(self, table, taints_data):
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Key", "Value", "Effect"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 解析并显示 taints 数据
        rows = []
        try:
            cmd = ["kubectl", "get", "node", self.node_name, "-o", "jsonpath='{.spec.taints[*]}'"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                # 解析 JSON 输出并填充表格
                import json
                taints = json.loads(result.stdout)
                for taint in taints:
                    rows.append([taint['key'], taint['value'], taint['effect']])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取 Taints 失败: {str(e)}")
        
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                table.setItem(i, j, QTableWidgetItem(str(value)))

    def get_taint_data(self):
        return {
            'key': self.key_input.text(),
            'value': self.value_input.text(),
            'effect': self.effect_combo.currentText()
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = LogHandler()
        self.setup_ui()
        self.check_requirements()

    def setup_ui(self):
        self.setWindowTitle("Kubernetes 节点管理工具")
        self.setMinimumSize(800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 添加按钮
        buttons = [
            ("查看所有节点状态", self.show_nodes),
            ("查看节点详细信息", self.describe_nodes),
            ("查看节点资源使用情况", self.show_resource_usage),
            ("添加新节点", self.add_node),
            ("停止 Minikube 集群", self.stop_cluster),
            ("启动 Minikube 集群", self.start_cluster),
            ("重置 Minikube 集群", self.reset_cluster),
            ("查看节点 taints", self.show_taints),
            ("添加节点 taint", self.add_taint),
            ("删除节点 taint", self.remove_taint)
        ]
        
        for text, slot in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def check_requirements(self):
        tools = ['minikube', 'kubectl']
        missing = []
        for tool in tools:
            try:
                subprocess.run(['which', tool], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing.append(tool)
        
        if missing:
            QMessageBox.critical(self, "错误", f"未安装必要工具: {', '.join(missing)}")
            sys.exit(1)

    def run_command(self, title, command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            QMessageBox.information(self, title, result.stdout)
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"命令执行失败: {e.stderr}")

    class NodesTableDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("节点状态")
            self.setMinimumSize(800, 400)
            self.setup_ui()
            self.refresh_data()
        
        def setup_ui(self):
            layout = QVBoxLayout()
            
            # 创建表格
            self.table = QTableWidget()
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["名称", "状态", "角色", "运行时间", "版本"])
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
            # 添加刷新按钮
            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(self.refresh_data)
            
            layout.addWidget(self.table)
            layout.addWidget(refresh_btn)
            self.setLayout(layout)
        
        def refresh_data(self):
            try:
                result = subprocess.run(
                    ["kubectl", "get", "nodes", "--no-headers"],
                    capture_output=True, text=True, check=True
                )
                
                # 清空表格
                self.table.setRowCount(0)
                
                # 填充数据
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                        
                    parts = line.split()
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    
                    for col, value in enumerate(parts[:5]):
                        item = QTableWidgetItem(value)
                        self.table.setItem(row, col, item)
                        
            except subprocess.CalledProcessError as e:
                QMessageBox.warning(self, "错误", f"获取节点信息失败: {e.stderr}")
    
    # 在 MainWindow 类中修改 show_nodes 方法：
    def show_nodes(self):
        dialog = NodesTableDialog(self)
        dialog.exec()

    def describe_nodes(self):
        self.run_command("节点详细信息", ["kubectl", "describe", "nodes"])

    def show_resource_usage(self):
        self.run_command("资源使用情况", ["kubectl", "top", "nodes"])

    def add_node(self):
        try:
            subprocess.run(["minikube", "node", "add", "--worker=true"], check=True)
            self.show_nodes()
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"添加节点失败: {e.stderr}")

    def stop_cluster(self):
        try:
            subprocess.run(["minikube", "stop"], check=True)
            QMessageBox.information(self, "成功", "Minikube 集群已停止")
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"停止集群失败: {e.stderr}")

    def start_cluster(self):
        try:
            subprocess.run(["minikube", "start"], check=True)
            QMessageBox.information(self, "成功", "Minikube 集群已启动")
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"启动集群失败: {e.stderr}")

    def reset_cluster(self):
        reply = QMessageBox.question(self, "确认", "确定要重置 Minikube 集群吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.run(["minikube", "delete"], check=True)
                subprocess.run(["minikube", "start"], check=True)
                QMessageBox.information(self, "成功", "Minikube 集群已重置")
            except subprocess.CalledProcessError as e:
                QMessageBox.warning(self, "错误", f"重置集群失败: {e.stderr}")

    def show_taints(self):
        self.run_command("Taints 信息", 
                        ["kubectl", "get", "nodes", "-o", 
                         "custom-columns=NAME:.metadata.name,TAINTS:.spec.taints"])

    def add_taint(self):
        # 获取节点列表
        try:
            result = subprocess.run(["kubectl", "get", "nodes", "--no-headers", 
                                   "-o", "custom-columns=NAME:.metadata.name"],
                                  capture_output=True, text=True, check=True)
            nodes = result.stdout.strip().split('\n')
            
            if not nodes:
                QMessageBox.warning(self, "错误", "没有可用的节点")
                return
            
            # 选择节点
            node_dialog = QDialog(self)
            node_dialog.setWindowTitle("选择节点")
            layout = QVBoxLayout(node_dialog)
            
            node_combo = QComboBox()
            node_combo.addItems(nodes)
            layout.addWidget(node_combo)
            
            buttons = QHBoxLayout()
            ok_button = QPushButton("确定")
            ok_button.clicked.connect(node_dialog.accept)
            cancel_button = QPushButton("取消")
            cancel_button.clicked.connect(node_dialog.reject)
            buttons.addWidget(ok_button)
            buttons.addWidget(cancel_button)
            layout.addLayout(buttons)
            
            if node_dialog.exec() == QDialog.DialogCode.Accepted:
                node_name = node_combo.currentText()
                taint_dialog = TaintDialog(node_name, self)
                if taint_dialog.exec() == QDialog.DialogCode.Accepted:
                    taint_data = taint_dialog.get_taint_data()
                    cmd = ["kubectl", "taint", "nodes", node_name,
                          f"{taint_data['key']}={taint_data['value']}:{taint_data['effect']}"]
                    self.run_command("添加 Taint", cmd)
                    self.logger.log(f"添加 Taint: {node_name} - {taint_data}")
                    
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"获取节点列表失败: {e.stderr}")

    def remove_taint(self):
        try:
            # 获取节点列表
            result = subprocess.run(["kubectl", "get", "nodes", "--no-headers", 
                                   "-o", "custom-columns=NAME:.metadata.name"],
                                  capture_output=True, text=True, check=True)
            nodes = result.stdout.strip().split('\n')
            
            if not nodes:
                QMessageBox.warning(self, "错误", "没有可用的节点")
                return
            
            # 选择节点
            node_dialog = QDialog(self)
            node_dialog.setWindowTitle("选择节点")
            layout = QVBoxLayout(node_dialog)
            
            node_combo = QComboBox()
            node_combo.addItems(nodes)
            layout.addWidget(node_combo)
            
            buttons = QHBoxLayout()
            ok_button = QPushButton("确定")
            ok_button.clicked.connect(node_dialog.accept)
            cancel_button = QPushButton("取消")
            cancel_button.clicked.connect(node_dialog.reject)
            buttons.addWidget(ok_button)
            buttons.addWidget(cancel_button)
            layout.addLayout(buttons)
            
            if node_dialog.exec() == QDialog.DialogCode.Accepted:
                node_name = node_combo.currentText()
                # 获取该节点的 taints
                result = subprocess.run(["kubectl", "get", "node", node_name, 
                                       "-o", "jsonpath='{.spec.taints[*]}'"],
                                      capture_output=True, text=True, check=True)
                
                if not result.stdout:
                    QMessageBox.information(self, "提示", "该节点没有 Taint")
                    return
                
                import json
                taints = json.loads(result.stdout)
                
                # 显示 taint 选择对话框
                taint_dialog = QDialog(self)
                taint_dialog.setWindowTitle("选择要删除的 Taint")
                layout = QVBoxLayout(taint_dialog)
                
                taint_combo = QComboBox()
                taint_combo.addItem("删除所有 Taints", "all")
                for taint in taints:
                    text = f"{taint['key']}={taint['value']}:{taint['effect']}"
                    taint_combo.addItem(text, taint['key'])
                layout.addWidget(taint_combo)
                
                buttons = QHBoxLayout()
                ok_button = QPushButton("确定")
                ok_button.clicked.connect(taint_dialog.accept)
                cancel_button = QPushButton("取消")
                cancel_button.clicked.connect(taint_dialog.reject)
                buttons.addWidget(ok_button)
                buttons.addWidget(cancel_button)
                layout.addLayout(buttons)
                
                if taint_dialog.exec() == QDialog.DialogCode.Accepted:
                    taint_key = taint_combo.currentData()
                    if taint_key == "all":
                        for taint in taints:
                            cmd = ["kubectl", "taint", "nodes", node_name, f"{taint['key']}-"]
                            self.run_command("删除 Taint", cmd)
                    else:
                        cmd = ["kubectl", "taint", "nodes", node_name, f"{taint_key}-"]
                        self.run_command("删除 Taint", cmd)
                    
                    self.logger.log(f"删除 Taint: {node_name} - {taint_key}")
                    
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "错误", f"操作失败: {e.stderr}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"操作失败: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())