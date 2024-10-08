import serial
import threading
from data_pub.uservo import UartServoManager
# from uservo import UartServoManager
import time
from collections import deque
import math
from scipy.interpolate import interp1d
import numpy as np
import matplotlib.pyplot as plt

READ_TIME_MINIMUM = 1/80

def plot_data(data,name):
    data = np.array(data)
    # 创建一个图表和一个轴对象
    fig, ax = plt.subplots()

    # 对于每一维数据（总共n维），绘制一条曲线
    for i in range(data.shape[1]):
        ax.plot(data[:, i], label=f"Dim {i+1}")

    # 添加图例
    ax.legend(loc="upper right")

    # 添加标签和标题
    plt.xlabel("Time Steps")
    plt.ylabel("Value")
    plt.title(f"{name}")

    path = f"/home/h666/code/other/{name}.jpg"
    # 显示图表
    plt.savefig(path)
    print(f"saved fig in {path}")
    # plt.show()

def action_interpolation(robot_pose, action, interpolate_factor):
    x_points = np.array([0, 1])
    dims = len(robot_pose)
    interpolate_nums = math.ceil(interpolate_factor) + 1

    # 生成插值点
    x_new = np.linspace(x_points[0], x_points[1], interpolate_nums)
    actions = []
    for dim in range(dims):
        y_points = np.array([robot_pose[dim], action[dim]])
        # 创建线性插值函数
        linear_interp = interp1d(x_points, y_points, kind="linear")
        y_new = linear_interp(x_new)
        actions.append(y_new)
    actions = np.array(actions)
    actions = actions.transpose()
    actions = actions.tolist()
    return actions[1:]


class MasterRobot:

    def __init__(self, robot_name, printer, read_time, publish_time):
        self.joint_pos = None
        self.grip_percentage = None
        self.threads = None
        self.plt_read_data = []
        self.plt_publish_data = []
        self.robot_name = robot_name
        self.printer = printer
        self.read_time = read_time
        self.read_data_state = 0
        self.arm_data_deque = deque(maxlen=1000)
        self.last_arm_data = None
        self.interpolate_factor = read_time / publish_time
        self.printer(f"{self.interpolate_factor=}")
        self.start_read_event = [threading.Event()]*7
        self.read_bot_state = [0]*7
        if self.robot_name == "master_left":
            self.SERVO_PORTS_ARM = [
                "/dev/ttyCH9344USB0",
                "/dev/ttyCH9344USB1",
                "/dev/ttyCH9344USB2",
                "/dev/ttyCH9344USB3",
                "/dev/ttyCH9344USB4",
                "/dev/ttyCH9344USB5",
            ]
            # self.SERVO_PORTS_GRIPPER = ["/dev/ttyCH9344USB6", "/dev/ttyCH9344USB7"]
            self.SERVO_PORTS_GRIPPER = ["/dev/ttyCH9344USB6"]
            self.SERVO_IDS_ARM = [0, 1, 2, 3, 4, 5]
            # self.SERVO_IDS_GRIPPER = [6, 17]
            self.SERVO_IDS_GRIPPER = [6]
            self.MASTER_HOME_POS_ARM = [6, 4, -6, -4, 91, -2]
            self.MASTER_OPEN = -21.3
            self.MASTER_CLOSE = -62
            self.SLAVE_OPEN = 170
            self.SLAVE_CLOSE = -111

        elif self.robot_name == "master_right":
            self.SERVO_PORTS_ARM = [
                "/dev/ttyCH9344USB8",
                "/dev/ttyCH9344USB9",
                "/dev/ttyCH9344USB10",
                "/dev/ttyCH9344USB11",
                "/dev/ttyCH9344USB12",
                "/dev/ttyCH9344USB13",
            ]
            # self.SERVO_PORTS_GRIPPER = ["/dev/ttyCH9344USB14", "/dev/ttyCH9344USB15"]
            self.SERVO_PORTS_GRIPPER = ["/dev/ttyCH9344USB14"]
            self.SERVO_IDS_ARM = [10, 11, 12, 13, 14, 15]
            # self.SERVO_IDS_GRIPPER = [16, 7]
            self.SERVO_IDS_GRIPPER = [16]
            self.MASTER_HOME_POS_ARM = [-46, 93, -82, -4, -96, 14]
            self.MASTER_OPEN = 5
            self.MASTER_CLOSE = 59
            self.SLAVE_OPEN = 115
            self.SLAVE_CLOSE = -165

        self.MASTER_HOME_POS_GRIPPER = [self.MASTER_OPEN, self.SLAVE_OPEN]
        self.SLAVE_HOME_POS_ARM = [
            45.0,
            -90.0,
            -90.0,
            -0.0,
            90.0,
            0.0,
        ]  # 从机械臂初始角度
        self.SERVO_BAUDRATE = 115200
        self.uart_managers_arm = []
        self.uart_managers_gripper = []

    def plot(self):
        plot_data(self.plt_read_data,f"{self.robot_name}_read_data")
        plot_data(self.plt_publish_data,f"{self.robot_name}_publish_data")

    def initialize_servos(self):
        def initialize_servo_port(i,port):
            try:
                self.printer(f"初始化机械臂串口 {port}")
                uart = serial.Serial(
                    port=port,
                    baudrate=self.SERVO_BAUDRATE,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=0,
                )
                self.uart_managers_arm[i] = UartServoManager(uart)
                self.printer(f"机械臂串口 {port} 初始化成功")
            except serial.SerialException as e:
                self.printer(f"机械臂串口 {port} 初始化失败: {e}")

        def initialize_gripper_port(i,port):
            try:
                self.printer(f"初始化夹爪串口 {port}")
                uart = serial.Serial(
                    port=port,
                    baudrate=self.SERVO_BAUDRATE,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=0,
                )
                self.uart_managers_gripper[i]=UartServoManager(uart)
                self.printer(f"夹爪串口 {port} 初始化成功")
            except serial.SerialException as e:
                self.printer(f"夹爪串口 {port} 初始化失败: {e}")
        
        self.uart_managers_arm = [0]*len(self.SERVO_PORTS_ARM)
        self.uart_managers_gripper = [0]*len(self.SERVO_PORTS_GRIPPER)
        threads_list = []
        for i, port in enumerate(self.SERVO_PORTS_ARM):
            t = threading.Thread(
                target=initialize_servo_port, args=(i,port)
            )
            threads_list.append(t)
            t.start()

        for i, port in enumerate(self.SERVO_PORTS_GRIPPER):
            t = threading.Thread(
                target=initialize_gripper_port, args=(i,port)
            )
            threads_list.append(t)
            t.start()
        
        for i, port in enumerate(threads_list):
            threads_list[i].join()
        pass



    def set_initial_positions(self):
        # 设置机械臂舵机初始角度ba
        self.printer("设置机械臂舵机初始角度")
        for i, uservo in enumerate(self.uart_managers_arm):
            uservo.set_servo_angle(
                self.SERVO_IDS_ARM[i],
                self.MASTER_HOME_POS_ARM[i],
                velocity=50.0,
                t_acc=500,
                t_dec=500,
            )
            uservo.wait()  # 等待舵机静止
            self.printer(
                f"舵机 {self.SERVO_IDS_ARM[i]} 设为初始角度 {self.MASTER_HOME_POS_ARM[i]}"
            )

        # 设置夹爪舵机初始角度
        self.printer("设置夹爪舵机初始角度")
        for i, uservo in enumerate(self.uart_managers_gripper):
            uservo.set_servo_angle(
                self.SERVO_IDS_GRIPPER[i], self.MASTER_HOME_POS_GRIPPER[i], interval=0
            )  # 设置舵机角度 极速模式
            uservo.wait()  # 等待舵机静止
            self.printer(
                f"舵机 {self.SERVO_IDS_GRIPPER[i]} 设为初始角度 {self.MASTER_HOME_POS_GRIPPER[i]}"
            )
        self.printer("设置夹爪舵机初始角度")
        for i, uservo in enumerate(self.uart_managers_gripper):
            uservo.set_servo_angle(
                self.SERVO_IDS_GRIPPER[i], self.MASTER_HOME_POS_GRIPPER[i], interval=0
            )  # 设置舵机角度 极速模式
            uservo.wait()  # 等待舵机静止
            self.printer(
                f"舵机 {self.SERVO_IDS_GRIPPER[i]} 设为初始角度 {self.MASTER_HOME_POS_GRIPPER[i]}"
            )

        # 初始化夹爪舵机
        for port in self.SERVO_PORTS_GRIPPER:
            try:
                self.printer(f"初始化串口 {port}")
                uart = serial.Serial(
                    port=port,
                    baudrate=self.SERVO_BAUDRATE,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=0,
                )
                self.uart_managers_gripper.append(UartServoManager(uart))
                self.printer(f"串口 {port} 初始化成功")
            except serial.SerialException as e:
                self.printer(f"串口 {port} 初始化失败: {e}")

    def set_damping_mode(self):
        # 设置读取角度的舵机为阻尼模式
        self.printer("设置夹爪读取角度的舵机为阻尼模式")
        self.uart_managers_gripper[0].set_damping(self.SERVO_IDS_GRIPPER[0], 10)
        self.printer(f"舵机 {self.SERVO_IDS_GRIPPER[0]} 阻尼模式设置完成")

        # 设置所有舵机为阻尼模式
        self.printer("设置机械臂舵机为阻尼模式")
        for i, uservo in enumerate(self.uart_managers_arm):
            uservo.set_damping(self.SERVO_IDS_ARM[i], 50)
            self.printer(f"舵机 {self.SERVO_IDS_ARM[i]} 阻尼模式设置完成")

    def stop_read_robot_data(self):
        for t in self.threads:
            t.join()

    def read_robot_data(self):
        # read data from master bot and interpolate the data
        if self.read_bot_state!= [1]*7:
            self.printer(f"{self.robot_name}_{self.read_bot_state=}")

        arm_data = self.joint_pos
        if not all(isinstance(i, float) for i in arm_data):
            self.printer(
                f"Not all elements in the first part of {self.robot_name} are floats"
            )
            return

        if self.last_arm_data == None:
            self.last_arm_data = arm_data

        interpolated_arm_data = action_interpolation(
            self.last_arm_data, arm_data, self.interpolate_factor
        )
        self.last_arm_data = arm_data
        # self.plt_read_data.append(arm_data.copy())
        if len(self.arm_data_deque) != 0:
            self.printer.error(f"arm_data_deque is not empty")
            return
        self.arm_data_deque.extend(interpolated_arm_data)
        self.read_bot_state= [0]*7
        for i in self.start_read_event:
            i.set()

    def get_robot_data(self):
        if len(self.arm_data_deque) == 0:
            self.read_robot_data()
        arm_data = self.arm_data_deque.popleft()
        # self.plt_publish_data.append(arm_data)
        return arm_data, self.grip_percentage[0]

    def start_read_robot_data(self):
        # Shared data between threads
        self.joint_pos = [0, 0, 0, 0, 0, 0]
        self.grip_percentage = [0]
        self.read_data_state = 1

        def read_servo_angle(index, uservo, servo_id):
            while 1:
                self.start_read_event[index].wait()
                ts = self.read_time - READ_TIME_MINIMUM
                if ts > 0:
                    time.sleep(ts)
                angle = uservo.query_servo_angle(servo_id)
                if index == 2:
                    self.joint_pos[index] = self.SLAVE_HOME_POS_ARM[index] + (
                        angle - self.MASTER_HOME_POS_ARM[index]
                    )
                else:
                    self.joint_pos[index] = self.SLAVE_HOME_POS_ARM[index] - (
                        angle - self.MASTER_HOME_POS_ARM[index]
                    )
                self.start_read_event[index].clear()
                self.read_bot_state[index] = 1
                

        def read_gripper_angle():
            while 1:
                # read data from master bot
                index = 6
                self.start_read_event[index].wait()
                ts = self.read_time - READ_TIME_MINIMUM
                if ts > 0:
                    time.sleep(ts)
                
                angle_gripper = self.uart_managers_gripper[0].query_servo_angle(
                    self.SERVO_IDS_GRIPPER[0]
                )
                self.grip_percentage[0] = (self.MASTER_OPEN - angle_gripper) / (
                    self.MASTER_OPEN - self.MASTER_CLOSE
                )
                # contrl puppet bot based on data
                # slave_angle = (
                #     self.grip_percentage[0] * (self.SLAVE_CLOSE - self.SLAVE_OPEN)
                #     + self.SLAVE_OPEN
                # )
                # self.uart_managers_gripper[1].set_servo_angle(
                #     self.SERVO_IDS_GRIPPER[1], slave_angle, interval=0
                # )
                self.start_read_event[index].clear()
                self.read_bot_state[index] = 1

        self.threads = []
        for i, uservo in enumerate(self.uart_managers_arm):
            t = threading.Thread(
                target=read_servo_angle, args=(i, uservo, self.SERVO_IDS_ARM[i])
            )
            self.threads.append(t)
            self.start_read_event[i].set()
            t.start()

        gripper_thread = threading.Thread(target=read_gripper_angle)
        self.threads.append(gripper_thread)
        self.start_read_event[6].set()
        gripper_thread.start()


class PuppetRobot:
    def __init__(self, robot_ip):
        self.robot_ip = robot_ip
        self.robot = Robot.RPC(self.robot_ip)

    def initialize_robot(self, joint_pos_o):
        # 机器人初始化
        self.printer("初始化从机械臂")
        ret = self.robot.MoveJ(joint_pos_o, tool=0, user=0, vel=10)
        self.printer("从机械臂就位", ret)
        # error, joint_pos = self.robot.GetActualJointPosDegree()
        # if error != 0:
        #     self.printer(f"获取机器人当前关节位置失败，错误码: {error}")
        #     sys.exit(1)
        # self.printer("机器人当前关节位置", joint_pos)

    def robot_control(self, joint_pos):
        ret = self.robot.ServoJ(joint_pos, cmdT=0.008)
