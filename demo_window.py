import tkinter as tk
from tkinter import ttk
import time
import threading
import queue
import sys
from io import StringIO

class TextRedirector:
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root
        self.closed = False

    def write(self, str):
        # 检查是否已经关闭
        if self.closed:
            return
        # 使用root.after将GUI更新操作调度到主线程
        try:
            self.root.after(0, self._write_to_widget, str)
        except:
            # 如果无法调度到主线程，直接忽略输出
            pass

    def _write_to_widget(self, str):
        """在主线程中实际执行GUI更新操作"""
        # 检查组件是否还存在
        try:
            if not self.closed and self.widget.winfo_exists():
                self.widget.configure(state='normal')
                self.widget.insert(tk.END, str)
                self.widget.configure(state='disabled')
                self.widget.see(tk.END)
        except:
            pass

    def close(self):
        self.closed = True

    def flush(self):
        pass

class ControlPanel:
    def __init__(self, root):
        self.root = root
        root.geometry("1000x700")  # 调整窗口大小，更宽一些以容纳所有控件
        self.root.title("模拟操作台")
        
        # 标记程序是否正在关闭
        self.closing = False

        # 创建主容器框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 设置主框架的行列配置
        self.main_frame.grid_columnconfigure(0, weight=3)  # 左侧区域权重
        self.main_frame.grid_columnconfigure(1, weight=3)  # 中间区域权重
        self.main_frame.grid_columnconfigure(2, weight=2, minsize=300)  # 右侧日志区域最小宽度300
        self.main_frame.grid_rowconfigure(0, weight=1)     # 垂直方向扩展

        # 创建左框架
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # 创建中框架
        self.middle_frame = ttk.Frame(self.main_frame)
        self.middle_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # 创建右侧日志框架
        self.log_frame = ttk.Frame(self.main_frame)
        self.log_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        # 在左框架中放置一个按钮
        button = ttk.Button(self.left_frame, text="点击按钮可以回到中值")
        button.pack(pady=5)

        # 在中框架中放置一个按钮
        button = ttk.Button(self.middle_frame, text="Power bool")
        button.pack(pady=5)

        self.max_val = 255  # 最大值
        self.current_gear = 1  # 初始挡位设置为1
        self.sliders = []  # 存储滑动条
        self.slider_labels = []  # 存储滑动条标签
        self.max_min_switches = []  # 存储布尔开关
        self.update_queue = {}  # 存储数据更新的字典
        self.previous_update_queue = {}  # 上次的更新字典
        self.bool_buttons = []  # 存储布尔按钮

        # 创建左侧滑动条和开关
        for i in range(8):  # 创建 8 对滑动条和布尔开关
            self.create_slider(f"Action{i+1}", self.left_frame)
            self.create_switch(f"Send Data {i+1}", self.left_frame)

        # 创建中间布尔值按钮
        for i in range(21):
            if i < 16:
                self.create_bool_button(f"power{i+1}", self.middle_frame)
            elif i == 16:
                continue
            else:
                self.create_bool_button(f"aux{i-17}", self.middle_frame)

        # 创建更新按钮
        self.create_update_button(self.middle_frame)

        # 创建换挡的滑动条（模拟换挡杆）
        self.gear_slider = tk.Scale(self.middle_frame, from_=1, to=6, orient="horizontal", length=200, sliderlength=20)
        self.gear_slider.set(1)  # 默认设置为 1 档
        self.gear_slider.pack(pady=5)

        # 添加标签，显示当前档位
        self.gear_label = ttk.Label(self.middle_frame, text="Power17")
        self.gear_label.pack(pady=5)

        # 设置滑动条事件监听，更新标签显示当前档位
        self.gear_slider.bind("<Motion>", self.update_gear)

        # 创建日志显示区域
        self.create_log_area()

        # 启动一个独立线程，每秒输出布尔按钮的状态并添加心跳标志
        self.bool_thread = threading.Thread(target=self.output_bool_status)
        self.bool_thread.daemon = True  # 确保主程序退出时，线程也会退出
        self.bool_thread.start()

        # 启动心跳线程，每隔1秒输出心跳值
        self.heartbeat_thread = threading.Thread(target=self.generate_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_value = 0  # 初始心跳值
        self.heartbeat_thread.start()

        # 重定向标准输出到文本框
        self.text_redirector = TextRedirector(self.log_text, self.root)
        sys.stdout = self.text_redirector

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """处理窗口关闭事件"""
        # 标记程序正在关闭
        self.closing = True
        
        # 关闭日志重定向
        if hasattr(self, 'text_redirector'):
            self.text_redirector.close()
        
        # 退出程序
        self.root.destroy()

    def create_slider(self, label, parent):
        # 创建滑动条框架
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        # 标签
        label_widget = ttk.Button(frame, text=label, command=lambda: self.reset_slider_by_label(label))
        label_widget.pack(side=tk.LEFT, padx=5)
        
        # 创建当前值标签
        current_val_label = ttk.Label(frame, text="127", width=5)
        current_val_label.pack(side=tk.RIGHT, padx=5)
        
        # 创建滑动条
        slider = tk.Scale(frame, from_=0, to=255, orient="horizontal", 
                         command=lambda val: self.update_slider_value(val, current_val_label))
        slider.set(127)  # 默认初始值为127
        slider.pack(fill=tk.X, padx=5)
        
        self.sliders.append((label, slider, current_val_label))

    def reset_slider_by_label(self, label):
        """通过标签重置对应的滑动条"""
        for slider_label, slider, label_widget in self.sliders:
            if slider_label == label:
                slider.set(127)
                label_widget.config(text="127")
                break

    def update_slider_value(self, value, label_widget):
        """更新滑动条的当前值标签"""
        label_widget.config(text=str(int(float(value))))

    def create_switch(self, label, parent):
        """创建布尔开关按钮"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        bool_var = tk.BooleanVar()
        switch = ttk.Checkbutton(frame, text=label, variable=bool_var)
        switch.pack(side=tk.LEFT, padx=5)
        self.max_min_switches.append(bool_var)

    def create_bool_button(self, label, parent):
        """创建布尔值按钮"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        bool_var = tk.BooleanVar()
        button = ttk.Checkbutton(frame, text=label, variable=bool_var)
        button.pack(side=tk.LEFT, padx=5)
        self.bool_buttons.append(bool_var)

    def create_update_button(self, parent):
        """创建更新按钮"""
        self.update_button = ttk.Button(parent, text="Update", command=self.update)
        self.update_button.pack(pady=10)

    def create_log_area(self):
        """创建日志显示区域"""
        log_label = ttk.Label(self.log_frame, text="运行日志", font=("Arial", 10, "bold"))
        log_label.pack(pady=5)
        
        # 创建文本框和滚动条
        log_text_frame = ttk.Frame(self.log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_text_frame, state='disabled', wrap=tk.WORD)
        log_scrollbar_y = ttk.Scrollbar(log_text_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar_x = ttk.Scrollbar(log_text_frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scrollbar_y.set, xscrollcommand=log_scrollbar_x.set)
        
        # 布局
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scrollbar_y.grid(row=0, column=1, sticky="ns")
        log_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        log_text_frame.grid_rowconfigure(0, weight=1)
        log_text_frame.grid_columnconfigure(0, weight=1)

    def update(self):
        """更新按钮点击事件"""
        try:
            # 获取滑动条的当前值并根据最大值计算
            max_vals = []
            for _, slider, _ in self.sliders:
                max_vals.append(int(slider.get() * self.max_val / 255))

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
        switches = [var for var in self.max_min_switches]
        for i, (max_val, bool_var) in enumerate(zip(max_vals, switches)):
            # 创建线程并启动，确保传递所有参数
            thread = threading.Thread(target=self.send_signal, args=(i, max_val, bool_var))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

    def output_bool_status(self):
        """每秒输出一次所有布尔值按钮的状态并加上心跳值"""
        while not self.closing:
            bool_status = []
            for i, bool_var in enumerate(self.bool_buttons):
                if i < 16:
                    bool_status.append(f"power{i+1} {'True' if bool_var.get() else 'False'}")
                    self.update_queue[f"power{i+1}"] = 'True' if bool_var.get() else 'False'
                elif i == 16:
                    continue
                else:
                    bool_status.append(f"aux{i-16} {'1' if bool_var.get() else '0'}")
                    self.update_queue[f"aux{i-16}"] = '1' if bool_var.get() else '0'
            
            time.sleep(0.1)  # 每秒输出一次布尔值状态

    def generate_heartbeat(self):
        """生成心跳值并循环"""
        while not self.closing:
            self.heartbeat_value = (self.heartbeat_value + 1) % 256  # 心跳值循环
            time.sleep(1)  # 每秒更新一次心跳值

    def getout_update_queue(self):
        """获取 update_queue 字典"""
        return self.update_queue.copy()

    def reset_slider(self, slider, label):
        """重置滑动条到中值并更新标签"""
        slider.set(127)  # 设置滑动条为中值
        label.config(text="127")  # 更新标签为中值

    def update_gear(self, event):
        """更新档位标签显示"""
        self.current_gear = self.gear_slider.get()
        self.gear_label.config(text=f"Power17：{int(self.current_gear)}")
        self.update_queue["power17"] = self.current_gear  # 更新 update_queue 字典