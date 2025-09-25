import signal
import sys
import threading
import os
import time
import random
import tkinter as tk
from tkinter import ttk

from simulation_processor import MainScreenSimulator
from demo_window import ControlPanel

# 全局关闭事件
shutdown_event = threading.Event()
# 声明 update_queue 为全局变量
update_queue = {}

def signal_handler(sig, frame):
    """处理操作系统信号（如 Ctrl+C）"""
    print("\n接收到关闭信号，正在停止模拟器...")
    shutdown_event.set()

def run_gui():
    global update_queue  # 在函数内部使用全局变量 update_queue
    """启动 Tkinter GUI"""
    root = tk.Tk()
    panel = ControlPanel(root)

    def check_update_queue():
        global update_queue  # 在函数内部使用全局变量 update_queue
        update_queue = panel.update_queue  # 获取 update_queue
        #print(update_queue)  # 打印当前 update_queue
        root.after(300, check_update_queue)  # 每1秒调用一次

    check_update_queue()  # 启动定时器

    root.mainloop()  # 启动 Tkinter 主循环


def run_simulator():
    """启动模拟器"""
    # 生成8位随机后缀（数字+大写字母）
    random_suffix = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
    config = {
        "broker": "127.0.0.1",
        "port": 1883,
        "username": "device5_client",
        "password": "111test",
        "control_topic_base": "LSVHJ133022221762/ctrl/",
        "safe_topic": "touch_screen/heartbeat",
        "client_id": f"main_screen_sim_{random_suffix}"
    }

    # 创建大屏模拟器对象
    simulator_mian_screen = MainScreenSimulator(
        broker=config["broker"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        client_id=config["client_id"],
        safe_topic=config["safe_topic"],
        control_topic_base=config["control_topic_base"],
        shutdown_event=shutdown_event,
        update_queue=update_queue
    )

    try:
        print("正在连接MQTT...")
        if simulator_mian_screen.connect():
            print("连接MQTT成功")
            if simulator_mian_screen.start_send_signal():
                print("启动发送信号线程和心跳线程")
                # 主线程等待关闭信号
                while not shutdown_event.is_set():
                    time.sleep(0.5)  # 每0.5s检测一次关闭信号
                    simulator_mian_screen.update_queue = update_queue
            else:
                print("启动信号发送失败")
        else:
            print("连接MQTT失败")

    except Exception as e:
        print(f"程序运行时发生错误: {e}", file=sys.stderr)

    finally:
        print("正在清理资源...")
        simulator_mian_screen.stop_send_signal()
        simulator_mian_screen.disconnect()
        print("资源清理完成，程序退出")

def main():
    """主函数"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动模拟器线程
    simulator_thread = threading.Thread(target=run_simulator)
    simulator_thread.daemon = True  # 守护线程，程序退出时自动清理
    simulator_thread.start()

    # 启动GUI线程
    gui_thread = threading.Thread(target=run_gui)
    gui_thread.daemon = True  # 守护线程，程序退出时自动清理
    gui_thread.start()

    # 等待线程结束
    gui_thread.join()
    simulator_thread.join()

if __name__ == "__main__":
    main()
