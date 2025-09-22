import paho.mqtt.client as mqtt
import random
import threading
import time
import json


class  MainScreenSimulator:
    def __init__(self, broker="127.0.0.1", port=1883, username="", password="", # 127.0.0.1 broker.emqx.io
                 client_id=None, safe_topic="", control_topic_base="",shutdown_event=None):
        self.broker=broker
        self.port=port      
        self.username=username
        self.password=password
        self.safe_topic=safe_topic
        self.control_topic_base=control_topic_base
        self.Flag_mqttConnected=0
        self.shutdown_event=shutdown_event

        # 创建 MQTT 客户端 ID
        if client_id is None:
            random_suffix=''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=6))   #话题后缀避重复
            self.client_id=f"main_screen_sim_{random_suffix}"
        else:
            self.client_id=client_id

        #创建MQTT客户端
        self.is_connected=False   #连接状态
        self.heartbeat_value=0   #记录心跳值
        self.running = False   #运行标志

        #控制信号
        # self.ACTION_1=127
        # self.ACTION_2=127
        # self.ACTION_3=127
        # self.ACTION_4=127
        # self.ACTION_5=127
        # self.ACTION_6=127
        # self.POWER_1=False
        # self.POWER_2=False
        # self.POWER_3=False
        # self.POWER_4=False
        # self.POWER_5=False
        # self.POWER_6=False
        # self.POWER_16=False
        # self.POWER_17=False
        # self.AUX_1=0
        # self.AUX_2=0

        #创建心跳线程和控制线程
        self.heartbeat_thread=None
        self.control_thread=None 
        #要发送的信号
        self.control_signals={
            "action1":127,
            "action2":127,
            "action3":127,
            "action4":127,
            "action5":127,
            "action6":127,
            "power1":False,
            "power2":False,
            "power3":False,
            "power4":False,
            "power5":False,
            "power6":False,
            "power16":False,
            "power17":False,
            "aux1":0,
            "aux2":0
        }

    def on_connect(self,client, userdata, flags, rc):
        if rc == 0:
            print("on_connect成功")
            self.is_connected = True
        else:
            print(f"on_connect失败，错误代码：{rc}")
        
    def on_disconnect(self,client, userdata, rc):
        print("已断开与MQTT服务器的连接")
        self.is_connected = False

    #连接MQTT服务器
    def connect(self):
        try:
            self.client=mqtt.Client(client_id=self.client_id, clean_session=True)
            self.client.on_connect=self.on_connect                        #连接MQTT服务器
            self.client.on_disconnect=self.on_disconnect                  #断开连接

            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)   #添加用户名和密码

            #连接MQTT
            #self.client.connect(self.broker, self.port, 60)
            #print(f"尝试连接到MQTT Broker")
            result= self.client.connect(self.broker, self.port, 60)
            
            # print(f"connect_1")
            if result != mqtt.MQTT_ERR_SUCCESS:
                 print(f"连接MQTT返回错误码: {result.name}({result.value})")
                 return False
            
            self.client.loop_start()          #启动MQTT客户端
            timeout = 10
            start_time = time.time()

            while not self.is_connected:
                time.sleep(0.1)

                if (time.time() - start_time) < timeout:
                    print("MQTT连接暂未超时，继续等待")
                else:
                     print("MQTT连接已超时")
                     self.Flag_mqttConnected=1
                
            
            if not self.Flag_mqttConnected:
                print(f"已连接到MQTT服务器")
            else:
                 print("MQTT连接不成功")
            
            
            
        
            return self.is_connected         #返回连接状态

        except Exception as e:
            print(f"连接MQTT Broker时发生错误: {e}")
            return False
           
    def disconnect(self):
        if self.client:
         self.client.loop_stop()
         self.client.disconnect()
         print("MQTT客户端已断开连接") 

    # def update_signal(self):    #方案一：随机更新控制信号并发送     方案二：控制每一个信号的发送
    #     """更新控制信号"""
    #     for i in range(1, 7):
    #         signal_name=f"action{i}"
    #         current_value = self.control_signals[signal_name]
    #         new_value = max(0, min(255, current_value + random.randint(-10, 10)))      #随机调整控制信号，模拟大屏发送的信号
    #         self.control_signals[signal_name] = new_value
    #         print(f"更新控制信号 {signal_name}: {current_value} -> {new_value}")

    #     for i in range(1, 7):
    #         signal_name=f"power{i}"
    #         self.control_signals[signal_name] = not self.control_signals[signal_name] 

    #     for i in range(1,3):
    #         signal_name=f"aux{i}"
    #         self.control_signals[signal_name] = random.randint(0, 3)

    def update_signal(self):
        """手动控制信号"""
        try:
            self.control_signals.update({
                "action1":129,
                "action2":130,
                "action3":127,
                "action4":127,
                "action5":127,
                "action6":127,
                "power1":True,
                "power2":False,
                "power3":False,
                "power4":False,
                "power5":False,
                "power6":False,
                "power16":False,
                "power17":1080,
                "aux1":1,
                "aux2":0   
            })
        except Exception as e:
             print(f"加载信号文件失败: {e}")

    def send_heartbeat(self):
        """发送心跳"""
        if not self.is_connected or not self.safe_topic:
           print(f"无法发送心跳,因为MQTT客户端未连接到服务器或没有安全主题")
           return False
        try:
            self.heartbeat_value = (self.heartbeat_value + 1) % 256   #0-255循坏发送心跳
            
            #发布心跳消息
            result,_ = self.client.publish(
                self.safe_topic, 
                str(self.heartbeat_value), # json
                qos=0, 
                retain=False
            )
            if result == mqtt.MQTT_ERR_SUCCESS:
                print(f"已发送心跳: {self.heartbeat_value}")
            else:
                print(f"发送心跳失败: {result}")
                return False
        except Exception as e:
            print(f"发送心跳消息时发生错误: {e}")
            return False
        
    def send_control_signals(self):
        """发送控制信号"""
        if not self.is_connected or not self.control_topic_base:
            print("无法发送控制信号,因为MQTT客户端未连接到服务器或者没有控制主题基础")
            return False
        
        try:
            #发送控制信号
            success_conut=0
            for signal_name, signal_value in self.control_signals.items():
                topic=f"{self.control_topic_base}{signal_name}"
                payload=str(signal_value)                                  #话题实际内容
                result,_=self.client.publish(topic, payload, qos=0, retain=False)
                if result==mqtt.MQTT_ERR_SUCCESS:
                    print(f"已发送控制信号: {topic} - {payload}")
                    success_conut+=1
                else:
                    print(f"发送控制信号失败: {topic} - {payload}")
        except Exception as e:
            print(f"发送控制信号时发生错误: {e}")
            return False
        
    def heartbeat_task(self):
        """心跳线程"""
        while self.running and not self.shutdown_event.is_set():
            if self.is_connected:  
                self.send_heartbeat()    
                print("已发送心跳") 
                time.sleep(2)     #每1秒发送一次心跳

    def control_task(self):
        """控制线程"""
        send_count=0
        while self.running and not self.shutdown_event.is_set():
            if self.is_connected:  
                self.update_signal()
                self.send_control_signals()
                send_count+=1
                print(f"已发送{send_count}个控制信号")  
                time.sleep(2)    #每1秒发送一次控制信号

    def start_send_signal(self):
        """启动发送控制信号和心跳"""
        self.running=True
        #启动心跳线程
        self.heartbeat_thread=threading.Thread(target=self.heartbeat_task,name="heartbeat_thread")
        self.heartbeat_thread.start()

        #启动控制线程
        self.control_thread=threading.Thread(target=self.control_task,name="control_thread")
        self.control_thread.start()

        print("已启动发送控制信号和心跳")
        return True
    
    def stop_send_signal(self):
        """停止发送控制信号和心跳"""
        self.running=False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1)      #join()函数等待线程结束，等待0.1s
        if self.control_thread:
            self.control_thread.join(timeout=1)
        print("已停止发送信号和心跳")

    
                         