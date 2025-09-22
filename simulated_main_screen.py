import signal
import sys
import threading
import os
import time
import random

from simulation_processor import MainScreenSimulator

# 全局关闭事件
shutdown_event = threading.Event()
def signal_handler(sig, frame):
    """处理操作系统信号（如 Ctrl+C）"""
    print("\n接收到关闭信号，正在停止模拟器...")
    shutdown_event.set()

def main():
     """主函数"""
     signal.signal(signal.SIGINT, signal_handler)
     signal.signal(signal.SIGTERM, signal_handler)

      # 生成8位随机后缀（数字+大写字母）

    #设置mqtt配置
     # 生成8位随机后缀（数字+大写字母）
     random_suffix = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
     config={
        "broker": "127.0.0.1",     #"192.168.1.64",
        "port": 1883,
        "username": "device5_client",
        "password": "111test",
        "control_topic_base": "LSVHJ133022221762/ctrl/",
        "safe_topic": "touch_screen/heartbeat",
        "client_id": f"main_screen_sim_{random_suffix}"
        }

    # 创建大屏模拟器对象
     simulator_mian_screen=MainScreenSimulator(
        broker=config["broker"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        client_id=config["client_id"],
        safe_topic=config["safe_topic"],
        control_topic_base=config["control_topic_base"],
        shutdown_event=shutdown_event
         )
        
     try:
        # 连接MQTT
        print("正在连接MQTT...")

        if simulator_mian_screen.connect():
            print("连接MQTT成功")
            
            # 启动信号发送
            if simulator_mian_screen.start_send_signal():
                print("启动发送信号线程和心跳线程")
                
                try:
                # 主线程等待关闭信号
                    while not shutdown_event.is_set():
                        time.sleep(0.5)    #每0.5s检测一次关闭信号
                except KeyboardInterrupt:
                      signal_handler(signal.SIGINT, None)  # 强制触发信号处理
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

if __name__ == "__main__":
    main()