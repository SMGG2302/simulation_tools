import tkinter as tk
import time
import threading
import queue
import sys
from io import StringIO
import json
import os


def resource_path(relative_path: str) -> str:
    """Return path to resource; works in dev and when bundled by PyInstaller."""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

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
                # 先判断插入前是否已经在末尾，只有在末尾时才自动滚动到末尾
                at_end_before = self.is_log_at_end()
                self.widget.configure(state='normal')
                self.widget.insert(tk.END, str)
                self.widget.configure(state='disabled')
                if at_end_before:
                    # 如果之前已经在末尾，插入新内容后保持跟随最新内容
                    self.widget.see(tk.END)
                # 否则保持当前滚动位置（不强制滚到底部）
        except:
            pass

    def is_log_at_end(self):
        """
        检查日志文本是否在最新位置（末尾）
        返回 True 如果在末尾，否则返回 False
        """
        # 获取当前视图的滚动位置
        # yview() 返回一个包含两个元素的元组: (top_position, bottom_position)
        # 如果 bottom_position >= 1.0，则表示视图在文本末尾
        try:
            yview_pos = self.widget.yview()
            # yview_pos[1] 表示视图底部相对于整个文本的位置（0.0 到 1.0）
            # 使用接近 1.0 的阈值来判断是否在末尾，容忍浮点误差
            return yview_pos[1] >= 0.99
        except:
            return True  # 出错时默认认为在末尾以便跟随最新日志
    
    def close(self):
        self.closed = True

    def flush(self):
        pass

class ControlPanel:
    def __init__(self, root):
        """初始化控制面板结构"""
        self.root = root
        # 默认配色（可以在运行时修改以统一主题）
        self.bg_color = "#f7f7f7"
        self.fg_color = "#000000"

        self.root.geometry("1300x900")  # 调整窗口大小，更宽一些以容纳所有控件
        self.root.title("模拟操作台")
        # 尝试设置主窗口图标（使用项目目录下的 simulator.ico）
        try:
            ico = resource_path('simulator.ico')
            if sys.platform == 'win32':
                self.root.iconbitmap(ico)
            else:
                try:
                    img = tk.PhotoImage(file=resource_path('simulator.png'))
                    self.root.iconphoto(True, img)
                    self._icon_image = img
                except Exception:
                    pass
        except Exception:
            pass
        
        # 标记程序是否正在关闭
        self.closing = False

        # 创建主容器框架
        self.main_frame = tk.Frame(self.root, bg=self.bg_color)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 设置主框架的行列配置
        self.main_frame.grid_columnconfigure(0, weight=3, minsize=300)  # action区域权重
        self.main_frame.grid_columnconfigure(1, weight=3, minsize=250)  # power区域权重
        self.main_frame.grid_columnconfigure(2, weight=3, minsize=200)  # aux区域权重
        self.main_frame.grid_columnconfigure(3, weight=1, minsize=450)  # 日志区域权重
        self.main_frame.grid_rowconfigure(1, weight=1)     # 垂直方向扩展，注意行号变为1

        # 创建顶部功能按钮框架
        self.top_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.top_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        # 创建action动作类框架
        self.action_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.action_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # 创建power动力类框架
        self.power_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.power_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        # 创建aux辅助类框架
        self.aux_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.aux_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")

        # 创建log日志框架
        self.log_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.log_frame.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")

        # action动作类框架说明
        left_label = tk.Label(self.action_frame, text="action", font=("Arial", 10, "bold"), bg=self.bg_color)
        left_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=10)

        # power动力类框架说明
        middle_label = tk.Label(self.power_frame, text="power", font=("Arial", 10, "bold"), bg=self.bg_color)
        middle_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=10)

        # aux辅助类框架说明
        right_label = tk.Label(self.aux_frame, text="aux", font=("Arial", 10, "bold"), bg=self.bg_color)
        right_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=10)

        """创建功能区域功能"""
        # 初始化滑动条参数
        self.max_val = 255  # 最大值
        self.current_gear = 1  # 初始挡位设置为1
        self.sliders = {}  # 存储滑动条,用于更新标签
        self.slider_values = {}  # 存储滑动条值，用于实时更新(避免在子线程中操作TK对象)
        self.bool_sliders = {}  # 存储布尔滑动条
        self.slider_labels = []  # 存储滑动条标签
        self.analog_enable_list = {} # 存储是否发送对应模拟量
        self.analog_threads = {} # 存储模拟量线程
        self.update_queue = {}  # 存储数据更新的字典
        self.previous_update_queue = {}  # 上次的更新字典
        self.ctrl_bool_buttons = {}  # 存储布尔按钮
        self.rec_bool_buttons = {}  # 存储接收信号按钮的字典
        self.update_queue['start_subscribe'] = False  # 初始化订阅状态为 False
        self.update_queue['connect_status'] = False
        self.update_queue['send_status'] = False
        self.update_queue['subscribe_status'] = False
        self.flag = False # 用于判断是否有按键按下的标志位
        self.heartbeat_interval = self.get_config().get("heartbeat_interval", 1.0) # 创建变量用于标签显示发送间隔
        self.broker_addr = self.get_config().get("broker", "127.0.0.1")
        self.device_serial = self.get_config().get("device_serial", "1")
        self.heartbeat_var = tk.StringVar(value=f"心跳状态: 停止, 发送间隔: {self.heartbeat_interval}s")
        self.broker_var = tk.StringVar(value=f"MQTT Broker: {self.broker_addr}")
        self.device_var = tk.StringVar(value=f"设备编号: {self.device_serial}")


        # 创建顶部功能按钮
        self.create_top_area()

        # 创建日志显示区域
        self.create_log_area()

        # 创建动作类区域
        self.creat_action_area()

        # 创建动力类区域
        self.creat_power_area()

        # 创建辅助类区域
        self.creat_aux_area()

        """启动心跳线程"""
        # 启动一个独立线程，每秒输出布尔按钮的状态并添加心跳标志
        self.bool_thread = threading.Thread(target=self.output_bool_status)
        self.bool_thread.daemon = True  # 确保主程序退出时，线程也会退出
        self.bool_thread.start()

        # 重定向标准输出到文本框
        self.text_redirector = TextRedirector(self.log_text, self.root)
        sys.stdout = self.text_redirector

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 在初始化完成后应用主题配色到所有 tk 子控件
        try:
            self.apply_theme(self.main_frame, bg=self.bg_color, fg=self.fg_color)
        except Exception:
            pass
    
    def apply_theme(self, widget, bg="#ffffff", fg="#000000"):
        """递归应用背景色/前景色到 widget 及其子孙控件（仅对 tk 小部件生效）。

        注意：某些控件不接受 bg/fg 参数（或使用不同的属性名），此函数会对可用属性进行尝试。
        """
        # 尝试设置当前 widget 的背景或前景颜色
        try:
            # 大多数 tk 小部件支持 configure(bg=...)
            widget.configure(bg=bg)
        except Exception:
            pass
        try:
            widget.configure(fg=fg)
        except Exception:
            pass

        # 对于 Text 小部件，使用 tag/直接配置背景前景
        if isinstance(widget, tk.Text):
            try:
                widget.configure(bg=bg, fg=fg)
            except Exception:
                pass

        # 递归处理子控件
        for child in widget.winfo_children():
            # 对于 Frame/Label/Button/Entry/Scale/Checkbutton 等常见控件，apply_theme 会尝试设置 bg/fg
            try:
                self.apply_theme(child, bg=bg, fg=fg)
            except Exception:
                # 忽略无法设置的子控件
                pass
    
    def create_canvas_scrollbar(self, frame, width=250):
        """创建画布和滚动条"""
        # 创建带滚动条的动作区域容器
        container = tk.Frame(frame)
        container.pack(fill=tk.BOTH, expand=True)
        
        # 创建画布和滚动条
        canvas = tk.Canvas(container, highlightthickness=0, width=width)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview, width=16)
        # 设置滚动条颜色使其更加明显
        scrollbar.configure(
            bg="#808080",          # 滚动条本身的颜色
            troughcolor="#c0c0c0", # 滚动条槽的颜色
            activebackground="#606060"  # 滚动条激活时的颜色
        )
        scrollable_frame = tk.Frame(canvas)

        # 配置画布和滚动区域
        scrollable_frame.bind(
            "<Configure>",
            lambda e:self.on_frame_configure(canvas)
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 打包画布和滚动条
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return scrollable_frame

    def on_frame_configure(self, canvas):
        """当滚动框架大小改变时更新画布的滚动区域"""
        # 强制设置一个足够大的滚动区域，确保滚动条始终可用
        canvas.configure(scrollregion=(0, 0, 300, 3000))
        
    def create_top_area(self):
        """创建顶部按钮"""
        # 添加功能按钮和心跳标签
        self.create_top_button("使用说明", self.guide_window)
        self.create_top_button("开始连接", self.start_connect)
        self.create_top_button("停止连接", self.stop_connect)
        self.create_top_button("开始发送", self.start_send)
        self.create_top_button("停止发送", self.stop_send)
        self.create_top_button("设置参数", self.set_parameters)
        self.create_top_button("订阅弹窗", self.show_subscriber_window)
        self.create_heartbeat_label()
        self.create_broker_label()
        self.create_device_label()

    def creat_action_area(self):
        """创建动作区域"""
        # 创建带滚动条的动作区域容器
        action_scrollable_frame = self.create_canvas_scrollbar(self.action_frame, width=250)
        # 创建左侧滑动条和开关
        for i in range(20):  # 创建 20 对滑动条和布尔开关
            self.create_slider(f"action{i+1}", action_scrollable_frame)
            
    def creat_power_area(self):
        """创建动力区域"""
        # 创建动力区域容器
        power_scrollable_frame = self.create_canvas_scrollbar(self.power_frame, width=200)
        # 创建中间布尔值按钮
        for i in range(40):
            self.create_bool_button(f"power{i+1}", power_scrollable_frame)

    def creat_aux_area(self):
        """创建辅助区域"""
        # 创建辅助函数按钮
        for i in range(10):
            self.create_bool_button(f"aux{i+1}", self.aux_frame)

    def create_log_area(self):
        """创建日志显示区域"""
        # 使用 fill 和内外边距，左对齐，避免文字被下方组件遮挡
        log_label = tk.Label(self.log_frame, text="发送日志", font=("Arial", 10, "bold"), bg=self.bg_color)
        # side='top' 并横向填充，减少被下方内容遮挡的可能性；适当增加下边距
        log_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=10)
        
        # 创建文本框和滚动条
        log_text_frame = tk.Frame(self.log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_text_frame, state='disabled', wrap=tk.WORD)
        log_scrollbar_y = tk.Scrollbar(log_text_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar_x = tk.Scrollbar(log_text_frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scrollbar_y.set, xscrollcommand=log_scrollbar_x.set)
        
        # 布局
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scrollbar_y.grid(row=0, column=1, sticky="ns")
        log_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        log_text_frame.grid_rowconfigure(0, weight=1)
        log_text_frame.grid_columnconfigure(0, weight=1)

    def create_top_button(self, text, command):
        """创建顶部功能按钮"""
        button = tk.Button(self.top_frame, text=text, command=command)
        button.pack(side=tk.LEFT, padx=5, pady=5)

    def create_heartbeat_label(self):
        """创建心跳标签"""
        label = tk.Label(self.top_frame, textvariable=self.heartbeat_var, font=("Arial", 10, "bold"))
        label.pack(side=tk.RIGHT, padx=5, pady=5)

    def create_broker_label(self):
        """创建MQTT服务器标签"""
        label = tk.Label(self.top_frame, textvariable=self.broker_var, font=("Arial", 10, "bold"))
        label.pack(side=tk.RIGHT, padx=5, pady=5)

    def create_device_label(self):
        """创建设备标签"""
        label = tk.Label(self.top_frame, textvariable=self.device_var, font=("Arial", 10, "bold"))
        label.pack(side=tk.RIGHT, padx=5, pady=5)

    def guide_window(self):
        """显示使用说明窗口"""


    def start_connect(self):
        """开始测试功能"""
        if self.update_queue and self.update_queue.get('connect_status') == True:
            print("MQTT连接已连接，请勿重复请求")
            return
        if self.update_queue and self.update_queue.get('start_mqtt') == True:
            print("发送连接请求已发出，请稍候")
            return
        try:
            # 将开始请求放入 update_queue，模拟器线程会检测并连接
            self.update_queue['start_mqtt'] = True
            print("开始测试: 已请求启动 MQTT 连接")
        except Exception as e:
            print(f"请求开始测试失败: {e}")

    def stop_connect(self):
        """停止测试功能"""
        if self.update_queue and self.update_queue.get('connect_status') == False:
            print("MQTT连接已断开，请勿重复请求")
            return
        if self.update_queue and self.update_queue.get('send_status') == True:
            print("仍处于发送中，请先停止")
            return
        if self.update_queue and self.update_queue.get('stop_send') == True:
            print("发送停止请求已发出，请稍候")
            return
        try:
            print("停止测试: 请求停止 MQTT 连接")
            # 将停止请求放入 update_queue，模拟器线程会检测并断开连接
            self.update_queue['stop_mqtt'] = True
            self.update_queue['connect_status'] = False
            print("已请求停止MQTT连接")
        except Exception as e:
            print(f"设置停止标志失败: {e}")

    def start_send(self):
        """开始发送功能"""
        if self.update_queue and self.update_queue.get('connect_status') == False:
            print("MQTT 未连接，请先启动 MQTT 连接")
        else:
            if self.update_queue and self.update_queue.get('start_send') == True:
                print("已经请求启动信号发送，请勿重复请求")
            else:
                self.update_queue['start_send'] = True
                self.heartbeat_var.set(f"心跳状态:发送, 发送间隔:{self.heartbeat_interval}s")
                print("已请求启动信号发送")

    def stop_send(self):
        """停止发送功能"""
        if self.update_queue and self.update_queue.get('connect_status') == False:
            print("MQTT 未连接，必然无法发送控制信号")
        else:
            if self.update_queue and self.update_queue.get('stop_send') == True:
                print("已经请求停止信号发送，请勿重复请求")
            else:
                self.update_queue['stop_send'] = True
                self.heartbeat_var.set("心跳状态:停止")
                print("已请求停止信号发送")

    def get_config(self):
        # 仅在 MQTT 未连接（connect_status == False）时允许设置
        if self.update_queue and self.update_queue.get('connect_status'):
            print("MQTT 正在连接或已连接，无法修改参数，请先停止 MQTT 后再设置。")
            return

        # 读取当前配置（config.json 相对于当前工作目录）以填充默认值
        cfg_path = os.path.abspath('config.json')
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            cfg = {}

        # 返回配置内容
        mqtt_cfg = cfg.get('mqtt', {})
        device_cfg = mqtt_cfg.get('device_config', {})
        current_broker = mqtt_cfg.get('broker', '')
        current_device_serial = device_cfg.get('device_serial', '')
        system_cfg = device_cfg.get('system', {})
        mqtt_timeout_cfg = system_cfg.get('mqtt_timeouts', {})
        current_heartbeat_interval = mqtt_timeout_cfg.get('heartbeat_detection_interval_sec', 1)
        self.heartbeat_interval = current_heartbeat_interval
        return {
            'broker': current_broker,
            'device_serial': current_device_serial,
            'heartbeat_interval': current_heartbeat_interval
        }
    def set_parameters(self):
        """设置参数功能：仅当 MQTT 未连接时生效，弹出窗口设置 broker、设备号和机型，并写回 config.json。"""
        # 仅在 MQTT 未连接（connect_status == False）时允许设置
        if self.update_queue and self.update_queue.get('connect_status'):
            print("MQTT 正在连接或已连接，无法修改参数，请先停止 MQTT 后再设置。")
            return

        # 读取当前配置（config.json 相对于当前工作目录）以填充默认值
        cfg_path = os.path.abspath('config.json')
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            cfg = {}

        mqtt_cfg = cfg.get('mqtt', {})
        device_cfg = mqtt_cfg.get('device_config', {})
        current_broker = mqtt_cfg.get('broker', '')
        current_device_serial = device_cfg.get('device_serial', '')
        system_cfg = device_cfg.get('system', {})
        mqtt_timeout_cfg = system_cfg.get('mqtt_timeouts', {})
        current_heartbeat_interval = mqtt_timeout_cfg.get('heartbeat_detection_interval_sec', '1.0')
        self.heartbeat_interval = current_heartbeat_interval

        # 创建弹窗
        top = tk.Toplevel(self.root)
        # 尝试给弹窗设置图标
        try:
            ico = resource_path('simulator.ico')
            if sys.platform == 'win32':
                top.iconbitmap(ico)
            else:
                try:
                    top.iconphoto(True, self._icon_image)
                except Exception:
                    pass
        except Exception:
            pass
        top.title('设置参数')
        top.geometry('400x250')

        tk.Label(top, text='Broker 地址:').pack(anchor='w', padx=10, pady=(10, 0))
        broker_var = tk.StringVar(value=current_broker)
        broker_entry = tk.Entry(top, textvariable=broker_var)
        broker_entry.pack(fill='x', padx=10, pady=5)

        tk.Label(top, text='设备号 (device_serial):').pack(anchor='w', padx=10, pady=(5, 0))
        device_var = tk.StringVar(value=current_device_serial)
        device_entry = tk.Entry(top, textvariable=device_var)
        device_entry.pack(fill='x', padx=10, pady=5)

        tk.Label(top, text='心跳发送间隔:').pack(anchor='w', padx=10, pady=(5, 0))
        heart_send = tk.StringVar(value=float(current_heartbeat_interval))
        heartbeat_entry = tk.Entry(top, textvariable=heart_send)
        heartbeat_entry.pack(fill='x', padx=10, pady=5)

        def on_confirm():
            nonlocal cfg
            new_broker = broker_var.get().strip()
            new_device = device_var.get().strip()
            new_heartbeat = heart_send.get().strip()

            if not new_broker:
                print('Broker 地址不能为空')
                return
            if not new_device:
                print('设备号不能为空')
                return            
            if not new_heartbeat:
                print('心跳间隔不能为空')
                return

            # 写回 config.json
            try:
                if not cfg:
                    cfg = {}
                if 'mqtt' not in cfg:
                    cfg['mqtt'] = {}
                cfg['mqtt']['broker'] = new_broker
                cfg['mqtt']['simulation_broker'] = new_broker
                cfg['mqtt']['device_config']['device_serial'] = new_device
                cfg['system']['mqtt_timeouts']['heartbeat_detection_interval_sec'] = new_heartbeat
                self.heartbeat_interval = new_heartbeat
                self.heartbeat_var.set(f"心跳状态: 停止, 心跳间隔: {new_heartbeat}s")
                self.broker_var.set(f"MQTT Broker: {new_broker}")
                self.device_var.set(f"设备编号: {new_device}")

                with open(cfg_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)

                print('已保存配置文件。请求主程序重新读取配置。')
                # 通知主程序重新加载配置
                try:
                    self.update_queue['_reload_config'] = True
                except Exception:
                    pass
                top.destroy()
            except Exception as e:
                print(f'保存配置失败: {e}')

        btn = tk.Button(top, text='确定', command=on_confirm)
        btn.pack(side='bottom', pady=12)

        # 使弹窗为模态（简单实现）
        top.transient(self.root)
        top.grab_set()

    def show_subscriber_window(self):
        """
        创建订阅管理窗口
        """
        # 启动窗口前检查mqtt连接状态，如果是未连接状态，则提示连接
        if self.update_queue.get('connect_status') == False:
            print("MQTT 未连接，请先连接。")
            return
        
        # 启动窗口前检查发送状态，如果是发送状态，则提示停止发送
        if self.update_queue.get('start_send') == True or self.update_queue.get('send_status') == True:
            print("正在发送信号，请先停止发送。")
            return
        
        # 如果弹窗已存在且还有效，则提升并返回
        if hasattr(self, '_subscriber_top') and self._subscriber_top and self._subscriber_top.winfo_exists():
            try:
                self._subscriber_top.deiconify()
                self._subscriber_top.lift()
                return
            except Exception:
                pass
        
        # 创建弹窗
        self.subscriber_top = tk.Toplevel(self.root)
        self._subscriber_top = self.subscriber_top
        self.subscriber_top.title("订阅管理")
        self.subscriber_top.geometry("1200x900")

        # 尝试设置图标（与主窗口一致）
        try:
            ico = resource_path('simulator.ico')
            if sys.platform == 'win32':
                self.subscriber_top.iconbitmap(ico)
            else:
                try:
                    subscriber_top.iconphoto(True, self._icon_image)
                except Exception:
                    pass
        except Exception:
            pass

        # 主容器（保持与主窗口相近的样式）
        main = tk.Frame(self.subscriber_top, bg=self.bg_color)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        # 行列配置
        main.grid_rowconfigure(0, weight=0)   # 顶行，放按钮
        main.grid_rowconfigure(1, weight=1)   # 第二行，可扩展
        main.grid_columnconfigure(0, weight=1, minsize=450)
        main.grid_columnconfigure(1, weight=1, minsize=150)
        main.grid_columnconfigure(2, weight=3, minsize=400)

        # 顶行功能按钮
        top_buttons_frame = tk.Frame(main)
        top_buttons_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0,6))
        # 放置若干功能按钮
        tk.Button(top_buttons_frame, text="开始订阅", width=12, command=self.start_subscribe).pack(side=tk.LEFT, padx=6)
        tk.Button(top_buttons_frame, text="停止订阅", width=12, command=self.stop_subscribe).pack(side=tk.LEFT, padx=6)

        # 左侧控制信号区
        ctrl_frame = tk.Frame(main, bg=self.bg_color)
        ctrl_frame.grid(row=1, column=0, sticky='nsew', padx=(0,6))

        ctrl_frame.grid_columnconfigure(0, weight=1)
        ctrl_frame.grid_columnconfigure(1, weight=1)
        ctrl_frame.grid_columnconfigure(2, weight=1)
        ctrl_frame.grid_rowconfigure(0, weight=0)
        ctrl_frame.grid_rowconfigure(1, weight=1)

        # 创建左侧区域说明标签
        ctrl_label = tk.Label(ctrl_frame, text='控制信号', font=('Arial', 10, 'bold'), bg=self.bg_color)
        ctrl_label.grid(row=0, column=0, columnspan=3, sticky='ew', padx=6, pady=(0,6))

        # 创建左侧控制信号分区
        ctrl_action_frame = tk.Frame(ctrl_frame, bg=self.bg_color)
        ctrl_action_frame.grid(row=1, column=0, sticky='nsew', padx=6, pady=(0,6))

        ctrl_power_frame = tk.Frame(ctrl_frame, bg=self.bg_color)
        ctrl_power_frame.grid(row=1, column=1, sticky='nsew', padx=6, pady=(0,6))
        
        ctrl_aux_frame = tk.Frame(ctrl_frame, bg=self.bg_color)
        ctrl_aux_frame.grid(row=1, column=2, sticky='nsew', padx=6, pady=(0,6))

        # 中间状态信号区
        status_frame = tk.Frame(main, bg=self.bg_color)
        status_frame.grid(row=1, column=1, sticky='nsew', padx=(0,6))

        # 创建中间区域说明标签
        status_label = tk.Label(status_frame, text='状态信号', font=('Arial', 10, 'bold'), bg=self.bg_color)
        status_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0,6))

        # 右侧日志区域
        log_frame = tk.Frame(main, bg=self.bg_color)
        log_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")

        # 日志区域说明标签
        log_label = tk.Label(log_frame, text='接收日志', font=('Arial', 10, 'bold'), bg=self.bg_color)
        log_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0,6))

        # 创建文本框和滚动条
        log_text_frame = tk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_text = tk.Text(log_text_frame, state='disabled', wrap=tk.WORD)
        log_scrollbar_y = tk.Scrollbar(log_text_frame, orient="vertical", command=log_text.yview)
        log_scrollbar_x = tk.Scrollbar(log_text_frame, orient="horizontal", command=log_text.xview)
        log_text.configure(yscrollcommand=log_scrollbar_y.set, xscrollcommand=log_scrollbar_x.set)
        
        # 布局
        log_text.grid(row=0, column=0, sticky="nsew")
        log_scrollbar_y.grid(row=0, column=1, sticky="ns")
        log_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        log_text_frame.grid_rowconfigure(0, weight=1)
        log_text_frame.grid_columnconfigure(0, weight=1)

        # 创建订阅功能按钮
        def create_rec_bool_button(label, parent):
            """创建布尔值按钮"""
            frame = tk.Frame(parent, bg=self.bg_color)
            frame.pack(fill=tk.X, pady=2)

            bool_var = tk.BooleanVar(value=False)

            default_bg = frame.cget('bg')
            def toggle(bvar=bool_var, btn=None):
                if self.update_queue.get('subscribe_status'):
                    if self.flag == False or bvar.get():
                        bvar.set(not bvar.get())
                        if bvar.get():
                            btn.config(relief='sunken', bg='lightgrey')
                            self.flag = True
                        else:
                            btn.config(relief='raised', bg=default_bg)
                            self.flag = False
                    else:
                        print("只能一次订阅一个主题")
                else:
                    print("请先开始订阅")

            btn = tk.Button(frame, text=label, relief='raised')
            btn.config(command=lambda b=btn: toggle(btn=b))
            btn.pack(side=tk.TOP, anchor='center', padx=5)
            self.rec_bool_buttons['rec_'+label] = bool_var

        # 创建状态订阅功能按钮
        create_rec_bool_button("internal", status_frame)
        create_rec_bool_button("external", status_frame)

        # 创建画布和滑动条
        ctrl_action_rolling_frame = self.create_canvas_scrollbar(ctrl_action_frame, width=100)
        ctrl_power_rolling_frame = self.create_canvas_scrollbar(ctrl_power_frame, width=100)
        
        # 创建控制订阅功能按钮
        for i in range(1, 20):
            create_rec_bool_button(f"action{i}", ctrl_action_rolling_frame)
        for i in range(1, 40):
            create_rec_bool_button(f"power{i}", ctrl_power_rolling_frame)
        for i in range(1, 11):
            create_rec_bool_button(f"aux{i}", ctrl_aux_frame)

        # 重定向标准输出到弹窗文本框：先保存当前 stdout 与现有 redirector，关闭时恢复
        try:
            prev_stdout = sys.stdout
            prev_redirector = getattr(self, 'text_redirector', None)
            subscriber_redirector = TextRedirector(log_text, self.subscriber_top)
            # 将当前 stdout 替换为弹窗 redirector（临时）
            sys.stdout = subscriber_redirector
            # 保存引用以便关闭时恢复
            self._subscriber_text_redirector = subscriber_redirector
            self._subscriber_prev_stdout = prev_stdout
            self._subscriber_prev_redirector = prev_redirector
        except Exception:
            pass

        # 模态化
        self.subscriber_top.transient(self.root)
        self.subscriber_top.grab_set()

        # 关闭回调：仅在当前 stdout 仍为弹窗 redirector 时恢复之前的 stdout
        def _on_subscriber_close():
            # 清除标志位
            self.flag = False
            # 停止订阅
            try:
                self.stop_subscribe()
            except Exception:
                pass
            # 恢复 stdout
            try:
                if getattr(sys, 'stdout', None) is getattr(self, '_subscriber_text_redirector', None):
                    # 恢复之前保存的 stdout（优先恢复具体保存的 prev_stdout）
                    if hasattr(self, '_subscriber_prev_stdout') and self._subscriber_prev_stdout:
                        sys.stdout = self._subscriber_prev_stdout
                    elif hasattr(self, '_subscriber_prev_redirector') and self._subscriber_prev_redirector:
                        sys.stdout = self._subscriber_prev_redirector
            except Exception:
                pass
            # 关闭弹窗 redirector
            try:
                if hasattr(self, '_subscriber_text_redirector'):
                    self._subscriber_text_redirector.close()
            except Exception:
                pass
            # 释放 grab 并销毁窗口
            try:
                self.subscriber_top.grab_release()
            except Exception:
                pass
            try:
                self.subscriber_top.destroy()
            except Exception:
                pass
            # 清理临时引用
            try:
                for attr in ('_subscriber_text_redirector', '_subscriber_prev_stdout', '_subscriber_prev_redirector', '_subscriber_top', 'subscriber_top'):
                    if hasattr(self, attr):
                        delattr(self, attr)
            except Exception:
                pass

        self.subscriber_top.protocol('WM_DELETE_WINDOW', _on_subscriber_close)

    def start_subscribe(self):
        """开始订阅"""
        if self.update_queue.get('start_subscribe') or self.update_queue.get('subscribe_status') == True:
            print("已经请求开始订阅或订阅已开始，请勿重复请求")
        else:
            print("开始订阅")
            self.update_queue['start_subscribe'] = True

    def stop_subscribe(self):
        """停止订阅"""
        if self.update_queue.get('stop_subscribe') or self.update_queue.get('subscribe_status') == False:
            print("已经请求停止订阅或订阅未开始，请勿重复请求")
        else:
            print("停止订阅")
            self.update_queue['stop_subscribe'] = True

    def on_closing(self):
        """处理窗口关闭事件"""
        print("收到窗口关闭请求")
        # 标记程序正在关闭
        self.closing = True
        
        # 关闭日志重定向
        if hasattr(self, 'text_redirector'):
            self.text_redirector.close()
        
        # 退出程序
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"关闭窗口时发生错误: {e}")

    def create_slider(self, label, parent):
        # 创建滑动条框架
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)

        # 顶部标题标签，显示例如: Action1
        title_label = tk.Label(frame, text=label, anchor='w')
        title_label.pack(fill=tk.X, padx=5, pady=(0, 2))

        # 横向容器：左侧放小按钮（发送,复位、-、+），右侧放滑动条
        row = tk.Frame(frame)
        row.pack(fill=tk.X, padx=5)

        # action发送按钮
        self._create_send_button(row, label='发送', action_name=label)
        
        # 小型复位按钮（置为中值）
        reset_btn = tk.Button(row, text='复位', width=4, command=lambda l=label: self.reset_slider_by_label(l))
        reset_btn.pack(side=tk.LEFT, padx=(0, 4), pady=(6, 0))

        # 减一按钮
        dec_btn = tk.Button(row, text='−', width=1, command=lambda s_label=label: self._inc_dec_slider(s_label, -1, self.sliders))
        dec_btn.pack(side=tk.LEFT, padx=(0, 4), pady=(6, 0))

        # 加一按钮
        inc_btn = tk.Button(row, text='+', width=1, command=lambda s_label=label: self._inc_dec_slider(s_label, 1, self.sliders))
        inc_btn.pack(side=tk.LEFT, padx=(0, 6), pady=(6, 0))

        # 滑动条，占据剩余空间
        slider = tk.Scale(row, from_=0, to=255, orient="horizontal",
                          command=lambda val, nm=label: self.update_slider_value(val, nm))
        slider.set(127)  # 默认初始值为127
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 存储：label 名称、slider 对象
        self.sliders[label]=slider
        # 存储：label 名称、slider 值
        self.slider_values[label]=slider.get()

    def reset_slider_by_label(self, label):
        """通过标签重置对应的滑动条"""
        for action_name in self.sliders:
            if action_name == label:
                self.sliders[action_name].set(127)
                break

    def update_slider_value(self, value, label_name):
        """更新滑动条的当前值标签，显示为 'LabelName：value'"""
        try:
            v = int(float(value))
            self.slider_values[label_name] = v
        except Exception:
            v = 0

    def _inc_dec_slider(self, label, delta, sliders):
        """根据 label 找到对应 slider，增减 delta（±1），并更新显示"""
        for slider_label in sliders:
            if slider_label == label:
                try:
                    cur = int(sliders[slider_label].get())
                except Exception:
                    cur = 0
                new = max(0, min(255, cur + delta))
                sliders[slider_label].set(new)
                self.slider_values[slider_label] = new
                break
    
    def _create_send_button(self, frame, label, action_name):
        """创建 action 发送按钮"""
        bool_var = tk.BooleanVar(value=False)

        default_bg = frame.cget('bg')
        def toggle(bvar=bool_var, btn=None):
            bvar.set(not bvar.get())
            if bvar.get(): # 按键按下
                btn.config(relief='sunken', bg='lightgrey')
                self.analog_enable_list[action_name] = bvar.get()
                self.update(action_name=action_name)
            else: # 按键抬起
                btn.config(relief='raised', bg=default_bg)
                self.analog_enable_list[action_name] = bvar.get()

        btn = tk.Button(frame, text=label, relief='raised')
        btn.config(command=lambda b=btn: toggle(btn=b))
        btn.pack(side=tk.LEFT, anchor='center', padx=5, pady=(6, 0))

    def create_bool_button(self, label, parent):
        """创建布尔值按钮"""
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)

        # 顶部标题标签，显示例如: Power1
        title_label = tk.Label(frame, text=label, anchor='w')
        title_label.pack(fill=tk.X, padx=5, pady=(0, 2))

        # 横向容器：左侧放小按钮（发送,复位、-、+），右侧放滑动条
        row = tk.Frame(frame)
        row.pack(fill=tk.X, padx=5)

        # 创建变量类型切换按钮
        self.create_switch_button(row, label)

        # 减一按钮
        dec_btn = tk.Button(row, text='−', width=1, command=lambda s_label=label: self._inc_dec_slider(s_label, -1, self.bool_sliders))
        dec_btn.pack(side=tk.LEFT, padx=(0, 4), pady=(6, 0))

        # 加一按钮
        inc_btn = tk.Button(row, text='+', width=1, command=lambda s_label=label: self._inc_dec_slider(s_label, 1, self.bool_sliders))
        inc_btn.pack(side=tk.LEFT, padx=(0, 6), pady=(6, 0))

        # 创建滑动条
        slider = tk.Scale(row, from_=0, to=1, orient="horizontal",
                          command=lambda val, nm=label: self.update_slider_value(val, nm))
        slider.set(0)  # 默认初始值为0
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 存储slider对象
        self.bool_sliders[label]=slider

    def create_switch_button(self, frame, label):
        """创建数据类型切换按钮"""
        def switch(btn=None):
            if btn.cget("text") == 'bool':
                btn.config(text = 'int')
                self.bool_sliders[label].config(from_=0, to=7, orient="horizontal")
            else:
                btn.config(text = 'bool')
                self.bool_sliders[label].config(from_=0, to=1, orient="horizontal")
            # 重置值
            self.bool_sliders[label].set(0)

        btn = tk.Button(frame, text='bool', relief='raised')
        btn.config(command=lambda b=btn: switch(btn=b))
        btn.pack(side=tk.LEFT, anchor='center', padx=5, pady=(6, 0))

    def update(self, action_name):
        """更新按钮点击事件"""
        try:
            # 将信号更新操作移到一个新的线程中，避免阻塞主线程
            update_thread = threading.Thread(target=self.send_control_signals, args=(action_name,))
            update_thread.daemon = True
            update_thread.start()
            print(f"已发送控制信号: {action_name}")

        except ValueError:
            print("无效的输入。请输入有效的数字。")

    def send_signal(self, action_name):
        """在子线程中发送控制信号"""
        while self.analog_enable_list[action_name]:  # 如果布尔值为 True，则发送该数据
            current_val = self.slider_values[action_name]
            self.update_queue['ctrl_'+action_name] = current_val
            time.sleep(1)

    def send_control_signals(self, action_name):
        """在新的线程中执行控制信号的发送并更新update_queue"""
        # 创建或者等待线程关闭线程
        if self.analog_threads.get(action_name) == None:
            thread = threading.Thread(target=self.send_signal, args=(action_name,))
            thread.start()
            self.analog_threads[action_name] = thread
            self.analog_threads[action_name].join()
            self.analog_threads[action_name] = None
        else:
            return

    def output_bool_status(self):
        """每秒输出一次所有布尔值按钮的状态并加上心跳值"""
        while not self.closing:
            for s in self.bool_sliders:
                if self.bool_sliders[s].cget("to") <= 1:
                    self.update_queue["ctrl_"+s] = True if self.bool_sliders[s].get() else False
                else:
                    self.update_queue["ctrl_"+s] = self.bool_sliders[s].get()
            for s, bool_var in self.rec_bool_buttons.items():
                self.update_queue[s] = True if bool_var.get() else False

            time.sleep(0.1)  # 每秒输出一次布尔值状态

    def getout_update_queue(self):
        """获取 update_queue 字典"""
        return self.update_queue.copy()

    def reset_slider(self, slider, label):
        """重置滑动条到中值并更新标签"""
        slider.set(127)  # 设置滑动条为中值
        label.config(text="127")  # 更新标签为中值

