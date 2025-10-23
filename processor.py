import paho.mqtt.client as mqtt
import random
import threading
import time
import json
import sys


class  MainScreenSimulator:
    def __init__(self, shutdown_event=None, update_queue=None, config_manager=None):
        self.Flag_mqttConnected=0
        self.shutdown_event=shutdown_event
        self.update_queue=update_queue
        self.config_manager=config_manager

        #创建MQTT客户端
        self.is_connected=False   #连接状态
        self.heartbeat_value=0   #记录心跳值
        self.running = False   #运行标志
        self.control_signals={} #要发送的信号         

        #创建心跳线程和控制线程
        self.heartbeat_thread=None
        self.control_thread=None 
        


    '''初始化结束，下面是MQTT客户端的功能模块'''    
    #连接MQTT服务器
    def connect(self):
        try:
            current_mqtt_config = self.config_manager.get_mqtt_config() # 获取最新配置
            broker = current_mqtt_config['broker']
            port = current_mqtt_config.get('port', 1883)
            username = current_mqtt_config['username']
            print(f"MQTT连接配置: {broker}:{port} - {username}")
            password = current_mqtt_config['password']
            client_id_prefix = current_mqtt_config.get('client_id_prefix', 'excavator_ctrl_')
            self.safe_topic = current_mqtt_config['safe_topic']
            self.control_topic_base = current_mqtt_config['control_topic_base']
            self.status_topics = current_mqtt_config['status_topics']
            self.internal_status_topic = self.status_topics.get('internal_status')
            self.external_status_topic = self.status_topics.get('external_equipment_status')


            random_suffix = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
            self.client_id = client_id_prefix + random_suffix

            self.client=mqtt.Client(client_id=self.client_id, clean_session=True)
            self.client.on_connect=self.on_connect                        #设置连接MQTT服务器的回调函数
            self.client.on_message=self.on_message                        #设置接收消息的回调函数
            self.client.on_disconnect=self.on_disconnect                  #设置断开MQTT服务器的回调函数
            if username and password:
                self.client.username_pw_set(username, password)   #添加用户名和密码
            
            result= self.client.connect(broker, port, 60) #连接MQTT
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                 print(f"连接MQTT返回错误码: {result.name}({result.value})")
                 return False
            
            self.client.loop_start()          #启动MQTT客户端
            timeout = 10
            start_time = time.time()
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                if not self.is_connected:
                    print("MQTT连接暂未超时，继续等待")  
        
            return self.is_connected         #返回连接状态

        except Exception as e:
            print(f"连接MQTT Broker时发生错误: {e}")
            return False
    
    # 连接的回调函数       
    def on_connect(self,client, userdata, flags, rc):
        if rc == 0:
            print("已连接到MQTT服务器")
            self.is_connected = True
        else:
            print(f"on_connect失败，错误代码：{rc}")
    
    # 断连的回调函数      
    def on_disconnect(self,client, userdata, rc):
        print("已断开与MQTT服务器的连接")
        self.is_connected = False
    
    '''以下开始是功能函数'''
    def start_send_signal(self):
        """启动发送控制信号和心跳"""
        self.running=True
        #启动心跳线程
        self.heartbeat_thread=threading.Thread(target=self.heartbeat_task,name="heartbeat_thread")
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

        #启动控制线程
        self.control_thread=threading.Thread(target=self.control_task,name="control_thread")
        self.control_thread.daemon = True
        self.control_thread.start()

        print("已启动发送控制信号和心跳")
        return True
    
    def start_rec_signal(self):
        """启动接收控制信号"""
        self.rec_running=True
        #启动状态信号接收线程
        self.status_thread=threading.Thread(target=self.status_task,name="status_thread")
        self.status_thread.daemon = True
        self.status_thread.start()

        print("已启动接收状态信号")
        return True
    
    def time_for_send_signal(self):
        get_mqtt_protocol_timeouts=self.config_manager.get_mqtt_protocol_timeouts()
        send_times = get_mqtt_protocol_timeouts.get('heartbeat_detection_interval_sec', 1)
        return send_times
    
    def get_config_manager(self):
        return self.config_manager
    
    #心跳发送功能函数
    def heartbeat_task(self):
        """心跳线程"""
        while self.running and not self.shutdown_event.is_set():
            if self.is_connected:  
                self.send_heartbeat()    
                print(f"当前发送速度: {self.time_for_send_signal()}")
            # 检查是否需要退出
            if self.shutdown_event.is_set():
                break
            # 使用较小的时间片以便更及时地响应关闭信号
            for _ in range(int(self.time_for_send_signal() / 0.1)):
                if self.shutdown_event.is_set():
                    break
                time.sleep(0.1)

    def send_heartbeat(self):
        """发送心跳"""
        if not self.is_connected or not self.safe_topic:
           print(f"无法发送心跳,因为MQTT客户端未连接到服务器或缺少安全主题")
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
                print(f"已发送心跳: {self.heartbeat_value} - {self.safe_topic}")
            else:
                print(f"发送心跳失败: {result}")
                return False
        except Exception as e:
            print(f"发送心跳消息时发生错误: {e}")
            return False

    #控制信号发送功能函数
    def control_task(self):
        """控制线程"""
        send_count=0
        while self.running and not self.shutdown_event.is_set():
            # 在发送控制信号前，检查外部指令（比如 GUI 写入的停止请求）
            try:
                if self.update_queue and '_stop_mqtt' in self.update_queue:
                    # 收到停止 MQTT 的请求，进行安全清理
                    print("收到停止 MQTT 请求，正在停止发送并断开连接...")
                    # 清理运行标志，停止心跳和控制线程
                    self.running = False
                    # 主动断开连接并停止 loop
                    try:
                        self.disconnect()
                    except Exception as e:
                        print(f"断开 MQTT 时出错: {e}")
                    # 移除停止标志以避免重复处理
                    try:
                        del self.update_queue['_stop_mqtt']
                    except:
                        pass
                    break

            except Exception as e:
                print(f"检查停止请求时出错: {e}")

            if self.is_connected:  
                self.send_control_signals()
                send_count+=1
                print(f"已发送{send_count}个控制信号")  
            # 检查是否需要退出
            if self.shutdown_event.is_set():
                break
            # 使用较小的时间片以便更及时地响应关闭信号
            for _ in range(int(self.time_for_send_signal() / 0.1)):
                if self.shutdown_event.is_set():
                    break
                time.sleep(0.1)

    def send_control_signals(self):
        """发送控制信号"""
        if not self.is_connected or not self.control_topic_base:
            print("无法发送控制信号,因为MQTT客户端未连接到服务器或者没有控制主题基础")
            return False
        
        try:
            #发送控制信号
            success_count=0
            if self.update_queue:
                for signal_name, signal_value in self.update_queue.items():
                    # 检查是否需要退出
                    if self.shutdown_event.is_set():
                        break
                    topic=f"{self.control_topic_base}{signal_name}"
                    payload=str(signal_value)                                  #话题实际内容
                    result,_=self.client.publish(topic, payload, qos=0, retain=False)
                    if result==mqtt.MQTT_ERR_SUCCESS:
                        print(f"已发送控制信号: {topic} - {payload}")
                        success_count+=1
                    else:
                        print(f"发送控制信号失败")
        except Exception as e:
            print(f"发送控制信号时发生错误: {e}")
            return False
        
    # 状态信号接收功能函数
    def status_task(self):
        """状态信号接收线程"""
        if self.rec_running and not self.shutdown_event.is_set():
            try:
                if self.update_queue.get('connect_status'):
                    if self.update_queue.get('subscribe_status') == True:
                        pass
                    else:
                        self.rec_status_signals()
                        print("已启动状态信号接收")
                else:
                    print("未连接到MQTT服务器，请检查网络连接")
            except Exception as e:
                print(f"状态信号接收线程发生错误: {e}")
                time.sleep(0.1)
        else:
            print("状态信号接收线程未运行或已收到关闭信号")

    def rec_status_signals(self):
        """接收状态信号"""
        if not self.is_connected or not self.status_topics:
            print("无法接收状态信号,因为MQTT客户端未连接到服务器或者没有状态主题")
            return False
        
        try:
            # 接收内部状态信号
            if self.internal_status_topic:
                print(f"正在订阅内部状态主题: {self.internal_status_topic}")
                result, _ = self.client.subscribe(self.internal_status_topic)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    print(f"已订阅内部状态主题: {self.internal_status_topic}")

                else:
                    print(f"订阅内部状态主题失败: {result}")
            else:
                print("未配置内部状态主题，跳过订阅")
                pass
            # 接收外部状态信号
            if self.external_status_topic:
                print(f"正在订阅外部设备状态主题: {self.external_status_topic}")
                result, _ = self.client.subscribe(self.external_status_topic)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    print(f"已订阅外部设备状态主题: {self.external_status_topic}")
                else:
                    print(f"订阅外部设备状态主题失败: {result}")
            else:
                print("未配置外部设备状态主题，跳过订阅")
                pass
                
        except Exception as e:
            print(f"接收状态信号时发生错误: {e}")
            return False

    def on_message(self, client, userdata, msg):
        """MQTT 消息到达回调：打印主题和负载，尝试 JSON 解析，并将结果放入 update_queue 供外层使用。"""
        try:
            topic = msg.topic
            payload_bytes = msg.payload
            try:
                payload = payload_bytes.decode('utf-8')
            except Exception:
                # 非 utf-8：以 repr 形式保存
                payload = repr(payload_bytes)

            # 打印原始接收内容
            print(f"接收消息: {topic} -> {payload}")

            # # 尝试解析 JSON
            # parsed = None
            # try:
            #     parsed = json.loads(payload)
            # except Exception:
            #     parsed = None

            # # 将接收到的数据记录到 update_queue，键名使用 recv:<topic>
            # try:
            #     key = f"recv:{topic}"
            #     # 如果解析成功，则放入解析后的结构，否则放原始字符串
            #     self.update_queue[key] = parsed if parsed is not None else payload
            # except Exception:
            #     pass
        except Exception as e:
            print(f"处理接收消息时发生错误: {e}")

    '''手动断连功能函数'''
    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            print("MQTT客户端已断开连接") 
    
    def stop_send_signal(self):
        """停止发送控制信号和心跳"""
        print("正在停止发送信号...")
        self.running=False
        
        # 等待线程结束，但设置超时时间
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=1)
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=1)
            
        print("已停止发送信号和心跳")

    def stop_rec_signal(self):
        """停止接收状态信号"""
        print("正在停止接收信号...")
        self.rec_running=False
        # 停止接收状态信号
        self.client.unsubscribe(self.internal_status_topic) 
        self.client.unsubscribe(self.external_status_topic)
        
        # 等待线程结束，但设置超时时间
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1)
            
        print("已停止接收状态信号")