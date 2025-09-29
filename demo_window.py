import tkinter as tk
from tkinter import ttk
import time
import threading
import queue

class ControlPanel:
    def __init__(self, root):
        self.root = root
        root.geometry("600x800")  # 调整窗口大小
        self.root.title("模拟操作台")

        # 创建主容器框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, padx=10, pady=10)

        # 设置主框架的行列配置，使其能够自适应父窗口大小
        self.main_frame.grid_columnconfigure(0, weight=2)  # 让左侧区域占更多空间
        self.main_frame.grid_columnconfigure(1, weight=2)  # 让右侧区域占更多空间
        self.main_frame.grid_rowconfigure(0, weight=1)  # 让行高度自适应

        # 创建左右分隔框架
        self.left_frame = ttk.Frame(self.main_frame, width=300, height=800)  # 增大左框架的大小
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.right_frame = ttk.Frame(self.main_frame, width=300, height=800)  # 增大右框架的大小
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # 设置最小大小，确保框架不会被压缩得过小
        self.left_frame.grid_propagate(False)  # 防止框架大小根据子组件调整
        self.right_frame.grid_propagate(False)  # 防止框架大小根据子组件调整

        # 在右框架中放置一个按钮
        button = ttk.Button(self.right_frame, text="Power bool")
        button.grid(row=0, column=0)

        self.max_val = 255  # 最大值
        self.sliders = []  # 存储滑动条
        self.slider_labels = []  # 存储滑动条标签
        self.max_min_switches = []  # 存储布尔开关
        self.update_queue = {}  # 存储数据更新的字典
        self.previous_update_queue = {}  # 上次的更新字典
        self.bool_buttons = []  # 存储布尔按钮

        row = 0  # 初始行号
        for i in range(8):  # 创建 8 对滑动条和布尔开关
            self.create_slider(f"Action{i+1}", row)  # 创建滑动条
            row += 1
            self.create_switch(f"Send Data {i+1}", row)  # 创建布尔按钮
            row += 1

        # 创建布尔值按钮
        for i in range(20):
            if i < 17:
                self.create_bool_button(f"power{i+1}", i+15)
            else:
                self.create_bool_button(f"aux{i-17}", i+15)

        # 创建更新按钮
        self.create_update_button()

        # 启动一个独立线程，每秒输出布尔按钮的状态并添加心跳标志
        self.bool_thread = threading.Thread(target=self.output_bool_status)
        self.bool_thread.daemon = True  # 确保主程序退出时，线程也会退出
        self.bool_thread.start()

        # 启动心跳线程，每隔1秒输出心跳值
        self.heartbeat_thread = threading.Thread(target=self.generate_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_value = 0  # 初始心跳值
        self.heartbeat_thread.start()

    def create_slider(self, label, row):
        """创建滑动条和标签"""
        label_widget = ttk.Label(self.left_frame, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=5)

        # 创建滑动条
        slider = tk.Scale(self.left_frame, from_=0, to=255, orient="horizontal", command=self.update_slider_value)
        slider.set(127)  # 默认初始值为50
        slider.grid(row=row, column=1, pady=5)

        # 创建当前值标签
        current_val_label = ttk.Label(self.left_frame, text="127")  # 初始值为50
        current_val_label.grid(row=row+1, column=1, pady=5)

        self.sliders.append(slider)
        self.slider_labels.append(current_val_label)

    def update_slider_value(self, value):
        """更新滑动条的当前值"""
        slider = self.sliders[-1]  # 当前变化的滑动条
        current_value = slider.get()
        self.slider_labels[-1].config(text=str(current_value))  # 只更新当前变化的标签

    def create_switch(self, label, row):
        """创建布尔开关按钮"""
        bool_var = tk.BooleanVar()
        switch = ttk.Checkbutton(self.left_frame, text=label, variable=bool_var)
        switch.grid(row=row, column=1, columnspan=2, pady=5)
        self.max_min_switches.append(bool_var)

    def create_bool_button(self, label, index):
        """创建布尔值按钮"""
        bool_var = tk.BooleanVar()
        button = ttk.Checkbutton(self.right_frame, text=label, variable=bool_var)
        button.grid(row=index-10, column=0, columnspan=2, pady=5)
        self.bool_buttons.append(bool_var)

    def create_update_button(self):
        """创建更新按钮"""
        self.update_button = ttk.Button(self.right_frame, text="Update", command=self.update)
        self.update_button.grid(row=30, column=0, columnspan=2, pady=10)

    def update(self):
        """更新按钮点击事件"""
        try:
            # 获取滑动条的当前值并根据最大值计算
            max_vals = [int(slider.get() * self.max_val / 255) for slider in self.sliders]

            # 将信号更新操作移到一个新的线程中，避免阻塞主线程
            update_thread = threading.Thread(target=self.send_control_signals, args=(max_vals,))
            update_thread.daemon = True
            update_thread.start()

        except ValueError:
            print("无效的输入。请输入有效的数字。")

    def send_signal(self, i, max_val, bool_var):
        """在子线程中发送控制信号"""
        if bool_var.get():  # 如果布尔值为 True，则发送该数据
            self.update_queue[f"action{i+1}"] = max_val


    def send_control_signals(self, max_vals):
        """在新的线程中执行控制信号的发送并更新update_queue"""
        threads = []
        for i, (max_val, bool_var) in enumerate(zip(max_vals, self.max_min_switches)):
            # 创建线程并启动，确保传递所有参数
            thread = threading.Thread(target=self.send_signal, args=(i, max_val, bool_var))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

    def output_bool_status(self):
        """每秒输出一次所有布尔值按钮的状态并加上心跳值"""
        while True:
            bool_status = []
            for i, bool_var in enumerate(self.bool_buttons):
                if i < 17:
                    bool_status.append(f"power{i+1} {'True' if bool_var.get() else 'False'}")
                    self.update_queue[f"power{i+1}"] = 'True' if bool_var.get() else 'False'
                else:
                    bool_status.append(f"aux{i-16} {'1' if bool_var.get() else '0'}")
                    self.update_queue[f"aux{i-16}"] = '1' if bool_var.get() else '0'
            
            time.sleep(0.1)  # 每秒输出一次布尔值状态


    def generate_heartbeat(self):
        """生成心跳值并循环"""
        while True:
            self.heartbeat_value = (self.heartbeat_value + 1) % 256  # 心跳值循环
            time.sleep(1)  # 每秒更新一次心跳值

    def getout_update_queue(self):
        """获取 update_queue 字典"""
        return self.update_queue.copy()

