import tkinter as tk
from tkinter import ttk
import time
import threading

class ControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("控制面板")

        # 创建控制信号界面
        self.control_frame = ttk.LabelFrame(self.root, text="控制面板", padding="10")
        self.control_frame.grid(row=0, column=0, padx=10, pady=10)

        # 创建最大值和最小值输入框（5组）
        for i in range(5):
            self.create_value_input(f"Max Value {i+1}", 0, 255, 127, i*2)
            self.create_value_input(f"Min Value {i+1}", 0, 255, 0, i*2+1)

        # 创建10个布尔值按钮
        self.bool_buttons = []
        for i in range(10):
            self.create_bool_button(f"Bool Button {i+1}", i)

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

    def create_value_input(self, label, min_val, max_val, default_val, row):
        """创建文本框和标签"""
        label_widget = ttk.Label(self.control_frame, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=5)
        
        # 创建文本框并插入默认值
        entry_widget = ttk.Entry(self.control_frame)
        entry_widget.insert(0, str(default_val))  # 设置默认值
        entry_widget.grid(row=row, column=1, pady=5)
        
        # 将每个输入框作为属性存储在实例中
        setattr(self, f"{label.lower().replace(' ', '_').replace('(', '').replace(')', '')}_entry", entry_widget)

    def create_bool_button(self, label, index):
        """创建布尔值按钮"""
        bool_var = tk.BooleanVar()
        button = ttk.Checkbutton(self.control_frame, text=label, variable=bool_var)
        button.grid(row=10 + index, column=0, columnspan=2, pady=5)
        self.bool_buttons.append(bool_var)

    def create_update_button(self):
        """创建更新按钮"""
        self.update_button = ttk.Button(self.control_frame, text="Update", command=self.update)
        self.update_button.grid(row=20, column=0, columnspan=2, pady=10)

    def update(self):
        """更新按钮点击事件"""
        try:
            # 获取用户输入的最大值、最小值
            max_vals = [int(getattr(self, f"max_value_{i+1}_entry").get()) for i in range(5)]
            min_vals = [int(getattr(self, f"min_value_{i+1}_entry").get()) for i in range(5)]

            # 获取选中的布尔按钮并输出相应的最大值和最小值
            for max_val, min_val, bool_var in zip(max_vals, min_vals, self.bool_buttons):
                if bool_var.get():  # 如果布尔值为 True，则发送该组最大值到最小值的数据
                    for i in range(max_val, min_val-1, -1):
                        print(i)  # 输出当前值
                        time.sleep(0.1)  # 设置时间间隔（10秒）
                        # 输出心跳标志
                        print(f"Heartbeat: {self.heartbeat_value}")
                        time.sleep(1)  # 心跳每秒输出一次
        except ValueError:
            print("无效的输入。请输入有效的数字。")

    def output_bool_status(self):
        """每秒输出一次所有布尔值按钮的状态并加上心跳值"""
        while True:
            bool_status = []
            for i, bool_var in enumerate(self.bool_buttons):
                bool_status.append(f"Bool Button {i+1} {'ON' if bool_var.get() else 'OFF'}")
            
            # 输出所有布尔值状态，并在最后输出当前心跳数值
            print(" | ".join(bool_status), f"Heartbeat: {self.heartbeat_value}")
            time.sleep(1)  # 每秒输出一次布尔值状态

    def generate_heartbeat(self):
        """生成心跳值并循环"""
        while True:
            self.heartbeat_value = (self.heartbeat_value + 1) % 256  # 心跳值循环
            time.sleep(1)  # 每秒更新一次心跳值

if __name__ == "__main__":
    root = tk.Tk()
    panel = ControlPanel(root)
    root.mainloop()
