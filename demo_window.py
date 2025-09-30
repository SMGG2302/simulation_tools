import customtkinter as ctk
import threading
import time

class ControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.geometry("730x820")  # 适当增加窗口的宽度
        self.root.title("模拟操作台")

        # 设置主题
        ctk.set_appearance_mode("dark")       # 可选 "light", "dark", "system"
        ctk.set_default_color_theme("blue")   # 可选 "blue", "green", "dark-blue"

        # 主框架（圆角）
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=10)  # 给最外层框架加圆角
        self.main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # 左右分区
        self.left_frame = ctk.CTkFrame(self.main_frame, width=400, height=800, corner_radius=10)  # 左边框架圆角
        self.left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.right_frame = ctk.CTkFrame(self.main_frame, width=300, height=800, corner_radius=10)  # 右边框架圆角
        self.right_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        self.left_frame.grid_propagate(False)
        self.right_frame.grid_propagate(False)

        # 按钮
        ctk.CTkButton(self.left_frame, text="点击按钮可以回到中值").grid(row=0, column=0, pady=2)
        ctk.CTkButton(self.right_frame, text="Power bool").grid(row=0, column=0, pady=2)

        self.max_val = 255
        self.current_gear = 1
        self.sliders = []
        self.slider_labels = []
        self.max_min_switches = []
        self.update_queue = {}
        self.previous_update_queue = {}
        self.bool_buttons = []

        row = 1
        for i in range(8):
            self.create_slider(f"Action{i+1}", row)
            row += 2  # 每两个控件占用一行
            self.create_switch(f"Send Data {i+1}", row)
            row += 2

        # 创建布尔值按钮
        for i in range(21):
            if i < 16:
                self.create_bool_button(f"power{i+1}", i+15)
            elif i < 18:
                continue
            else:
                self.create_bool_button(f"aux{i-17}", i+15)

        # 更新按钮
        self.create_update_button()

        # 启动线程
        self.bool_thread = threading.Thread(target=self.output_bool_status, daemon=True)
        self.bool_thread.start()

        self.heartbeat_thread = threading.Thread(target=self.generate_heartbeat, daemon=True)
        self.heartbeat_value = 0
        self.heartbeat_thread.start()

        # 换挡滑动条
        self.gear_slider = ctk.CTkSlider(self.right_frame, from_=0, to=6,
                                         number_of_steps=6,
                                         command=self.update_gear)
        self.gear_slider.set(0)
        self.gear_slider.grid(row=22, column=0, padx=5, pady=2)

        # 档位标签
        self.gear_label = ctk.CTkLabel(self.right_frame, text="Power17")
        self.gear_label.grid(row=21, column=0, padx=5, pady=2)

    def create_slider(self, label, row):
        slider = ctk.CTkSlider(self.left_frame, from_=0, to=255,
                               number_of_steps=255,
                               command=lambda val, s=len(self.sliders): self.update_slider_value(s, val))
        slider.set(127)
        slider.grid(row=row, column=1, pady=2, sticky="ew")  # 修改为填充左右

        current_val_label = ctk.CTkLabel(self.left_frame, text="127")
        current_val_label.grid(row=row-1, column=1, pady=2)  # 将数字显示在上方

        label_widget = ctk.CTkButton(self.left_frame, text=label,
                                     command=lambda s=slider, l=current_val_label: self.reset_slider(s, l))
        label_widget.grid(row=row, column=0, padx=2, pady=2)

        self.sliders.append(slider)
        self.slider_labels.append(current_val_label)

    def update_slider_value(self, index, value):
        self.slider_labels[index].configure(text=str(int(float(value))))

    def create_switch(self, label, row):
        bool_var = ctk.BooleanVar()
        switch = ctk.CTkCheckBox(self.left_frame, text=label, variable=bool_var)
        switch.grid(row=row, column=1, columnspan=2, pady=2, sticky="w")
        self.max_min_switches.append(bool_var)

    def create_bool_button(self, label, index):
        bool_var = ctk.BooleanVar()
        button = ctk.CTkCheckBox(self.right_frame, text=label, variable=bool_var)
        button.grid(row=index-10, column=0, pady=2, sticky="w")
        self.bool_buttons.append(bool_var)

    def create_update_button(self):
        self.update_button = ctk.CTkButton(self.right_frame, text="Update", command=self.update)
        self.update_button.grid(row=30, column=0, pady=5)

    def update(self):
        try:
            max_vals = [int(slider.get() * self.max_val / 255) for slider in self.sliders]
            threading.Thread(target=self.send_control_signals, args=(max_vals,), daemon=True).start()
        except ValueError:
            print("无效的输入")

    def send_signal(self, i, max_val, bool_var):
        if bool_var.get():
            self.update_queue[f"action{i+1}"] = max_val

    def send_control_signals(self, max_vals):
        threads = []
        for i, (max_val, bool_var) in enumerate(zip(max_vals, self.max_min_switches)):
            t = threading.Thread(target=self.send_signal, args=(i, max_val, bool_var))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def output_bool_status(self):
        while True:
            for i, bool_var in enumerate(self.bool_buttons):
                if i < 16:
                    self.update_queue[f"power{i+1}"] = 'True' if bool_var.get() else 'False'
                else:
                    self.update_queue[f"aux{i-16}"] = '1' if bool_var.get() else '0'
            time.sleep(0.1)

    def generate_heartbeat(self):
        while True:
            self.heartbeat_value = (self.heartbeat_value + 1) % 256
            time.sleep(1)

    def getout_update_queue(self):
        return self.update_queue.copy()

    def reset_slider(self, slider, label):
        slider.set(127)
        label.configure(text="127")

    def update_gear(self, value):
        self.current_gear = int(float(value))
        self.gear_label.configure(text=f"Power17: {self.current_gear}")
        self.update_queue["power17"] = self.current_gear


if __name__ == "__main__":
    root = ctk.CTk()
    app = ControlPanel(root)
    root.mainloop()
