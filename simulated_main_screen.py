import signal
import sys
import threading
import os
import time
import random
import tkinter as tk
from tkinter import ttk

from processor import MainScreenSimulator
from demo_window import ControlPanel
from config_manager import ConfigManager

# 全局关闭事件
shutdown_event = threading.Event()
# 声明 update_queue 为全局变量
update_queue = {}

def signal_handler(sig, frame):
    """处理操作系统信号（如 Ctrl+C）"""
    print("\n接收到关闭信号，等待关闭UI界面...")
    shutdown_event.set()

def run_gui(stop_flag):
    global update_queue  # 在函数内部使用全局变量 update_queue
    """启动 Tkinter GUI"""
    root = tk.Tk()
    panel = ControlPanel(root)
    
    def check_update_queue():
        global update_queue  # 在函数内部使用全局变量 update_queue
        update_queue = panel.update_queue  # 获取 update_queue
        if not stop_flag.is_set():
            root.after(100, check_update_queue)  # 每100ms调用一次

    check_update_queue()  # 启动定时器

    # 假设当GUI关闭时，stop_flag 会被设置
    def on_close():
        print("正在关闭GUI...")
        stop_flag.set()  # 设置停止标志
        shutdown_event.set()  # 同时设置全局关闭事件
        try:
            root.quit()  # 退出主循环
        except:
            pass
        try:
            root.destroy()  # 销毁根窗口
        except:
            pass

    root.protocol("WM_DELETE_WINDOW", on_close)  # 当窗口关闭时，设置停止标志并退出

    try:
        root.mainloop()  # 启动 Tkinter 主循环
        # 主循环结束后确保设置停止标志
        stop_flag.set()
        shutdown_event.set()
    except Exception as e:
        print(f"GUI运行时发生错误: {e}")

def run_simulator(stop_flag, config_manager):
    """启动模拟器"""
    # 创建大屏模拟器对象
    simulator_mian_screen = MainScreenSimulator(
        shutdown_event=shutdown_event,
        update_queue=update_queue,
        config_manager = config_manager
    )

    try:
        print("正在连接MQTT...")
        if simulator_mian_screen.connect():
            print("连接MQTT成功")
            if simulator_mian_screen.start_send_signal():
                print("启动发送信号线程和心跳线程")
                # 主线程等待关闭信号
                while not stop_flag.is_set() and not shutdown_event.is_set():  # 检查 stop_flag 是否被设置
                    time.sleep(0.01)  # 每0.01秒检测一次关闭信号
                    simulator_mian_screen.update_queue = update_queue
            else:
                print("启动信号发送失败")
        else:
            print("连接MQTT失败")

    except Exception as e:
        print(f"程序运行时发生错误: {e}", file=sys.stderr)

    finally:
        print("正在清理资源...")
        try:
            simulator_mian_screen.stop_send_signal()
            simulator_mian_screen.disconnect()
        except Exception as e:
            print(f"清理资源时发生错误: {e}")
        print("资源清理完成，程序退出")

def get_external_resource_path(relative_path):
    """获取exe文件所在目录的资源文件路径"""
    # 获取exe文件所在目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe文件
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是正常运行的Python脚本
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(application_path, relative_path)

def main():
    # 使用get_external_resource_path函数来获取exe所在目录的配置文件路径
    config_path = get_external_resource_path('config.json')
    print(f"断点-- 配置文件路径: {config_path}")

    # 初始化 ConfigManager (它内部会调用 get_logger，但此时 logger 还未配置)
    config_manager = ConfigManager(config_path=config_path)
    """主函数"""
    stop_flag = threading.Event()  # 创建一个线程事件作为停止标志

    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动模拟器线程
    simulator_thread = threading.Thread(target=run_simulator, args=(stop_flag,config_manager))
    simulator_thread.daemon = True  # 守护线程，程序退出时自动清理
    simulator_thread.start()

    # 启动GUI线程
    gui_thread = threading.Thread(target=run_gui, args=(stop_flag,))
    gui_thread.daemon = True  # 守护线程，程序退出时自动清理
    gui_thread.start()

    # 等待线程结束
    try:
        gui_thread.join()
        simulator_thread.join(timeout=2)  # 设置超时时间
    except KeyboardInterrupt:
        print("捕获到键盘中断，退出程序")
        stop_flag.set()  # 设置 stop_flag，通知所有线程停止
        shutdown_event.set()  # 设置全局关闭事件
        # 等待线程结束
        gui_thread.join(timeout=1)
        simulator_thread.join(timeout=1)
        exit(0)
    except Exception as e:
        print(f"等待线程结束时发生错误: {e}")
    finally:
        # 确保设置停止标志
        stop_flag.set()
        shutdown_event.set()
        print("程序已退出")
        # 强制退出程序
        try:
            os._exit(0)
        except:
            pass

if __name__ == "__main__":
    main()