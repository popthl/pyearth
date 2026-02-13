import sys
import numpy as np
import pyvista as pv
from pyvista import examples
import datetime
import re
import os
from skyfield.api import load, wgs84, utc
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QSplitter
from PyQt5.QtCore import Qt
from pyvistaqt import QtInteractor

class SatelliteOrbitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Satellite Orbit Simulation")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建分割器，用于调整左右widget的宽度
        splitter = QSplitter(Qt.Horizontal)
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(splitter)
        
        # 创建左侧容器，包含控制面板
        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        splitter.addWidget(self.left_container)  # 将左侧容器添加到分割器中
        
        # 设置左侧容器的初始大小
        splitter.setSizes([150, 1050])  # 左侧150，右侧1050，让3D窗口占据更多面积
        
        # 创建控制面板部件
        self.control_panel = QWidget()
        control_layout = QVBoxLayout(self.control_panel)
        left_layout.addWidget(self.control_panel)  # 控制面板占据左侧容器的全部空间
        
        # 添加控制面板标题
        control_title = QLabel("控制面板")
        control_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: gray;")
        control_title.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(control_title)
        
        # 创建3D场景部件
        self.plotter_widget = QtInteractor(central_widget)
        splitter.addWidget(self.plotter_widget)  # 将3D场景部件添加到分割器中
        
        # 添加仿真时间显示
        self.time_label = QLabel("仿真时间:")
        control_layout.addWidget(self.time_label)
        
        # 初始化仿真时间为当前时间
        self.simulation_time = datetime.datetime.now(datetime.timezone.utc)
        self.time_display_label = QLabel(self.simulation_time.strftime("%Y-%m-%d %H:%M:%S UTC"))
        self.time_display_label.setStyleSheet("font-family: monospace;")
        control_layout.addWidget(self.time_display_label)
        
        # 初始化地球自转速度
        self.earth_rotation_speed = 1.0
        
        # 保存日月和行星演员的引用
        self.solar_system_actors = {}
        
        # 加载de421.bsp文件
        print("正在加载de421.bsp文件...")
        self.planets = load('de421.bsp')
        print("成功加载de421.bsp文件")
        
        # 获取地球
        self.earth = self.planets['earth']
        
        # 获取时间尺度
        self.ts = load.timescale()
        
        # 仿真控制变量
        self.simulation_running = False
        self.simulation_step = 0
        self.timer = None
        
        # 保存上一次的GMST值，用于计算旋转角度差值
        self.last_gmst_rad = None
        
        # 添加显示/隐藏恒星的复选框
        from PyQt5.QtWidgets import QCheckBox
        self.stars_checkbox = QCheckBox("显示恒星")
        self.stars_checkbox.setChecked(True)  # 默认显示恒星
        self.stars_checkbox.stateChanged.connect(self.toggle_stars)
        control_layout.addWidget(self.stars_checkbox)
        
        # 添加显示/隐藏天球网格的复选框
        self.grid_checkbox = QCheckBox("显示天球网格")
        self.grid_checkbox.setChecked(True)  # 默认显示天球网格
        self.grid_checkbox.stateChanged.connect(self.toggle_sky_grid)
        control_layout.addWidget(self.grid_checkbox)
        
        # 添加显示/隐藏星座连线图的复选框
        self.constellations_checkbox = QCheckBox("显示星座连线图")
        self.constellations_checkbox.setChecked(True)  # 默认显示星座连线图
        self.constellations_checkbox.stateChanged.connect(self.toggle_constellations)
        control_layout.addWidget(self.constellations_checkbox)
        
        # 添加显示/隐藏日月和行星的复选框
        self.solar_system_checkbox = QCheckBox("显示日月和行星")
        self.solar_system_checkbox.setChecked(True)  # 默认显示日月和行星
        self.solar_system_checkbox.stateChanged.connect(self.toggle_solar_system)
        control_layout.addWidget(self.solar_system_checkbox)
        
        # 添加地球自转控制复选框
        self.earth_rotation_checkbox = QCheckBox("地球自转")
        self.earth_rotation_checkbox.setChecked(True)  # 默认选中，相机不动
        self.earth_rotation_checkbox.stateChanged.connect(self.toggle_earth_rotation)
        control_layout.addWidget(self.earth_rotation_checkbox)
        
        # 添加仿真控制按钮
        self.run_button = QPushButton("运行仿真")
        self.run_button.clicked.connect(self.run_simulation)
        control_layout.addWidget(self.run_button)
        
        self.pause_button = QPushButton("暂停仿真")
        self.pause_button.clicked.connect(self.pause_simulation)
        control_layout.addWidget(self.pause_button)
        
        # 添加仿真步长控制滑块
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(-7)
        self.slider.setMaximum(7)
        self.slider.setValue(1)  # 默认值为1，对应1s
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.valueChanged.connect(self.slider_callback)
        control_layout.addWidget(QLabel("仿真步长:"))
        control_layout.addWidget(self.slider)
        
        # 添加滑块值显示
        self.slider_value_label = QLabel("步长值: 1s")
        control_layout.addWidget(self.slider_value_label)
        
        # 定义步长映射
        self.step_mapping = {
            -7: -86400,  # -24h
            -6: -21600,  # -6h
            -5: -3600,   # -3600s
            -4: -300,    # -300s
            -3: -60,     # -60s
            -2: -10,     # -10s
            -1: -1,      # -1s
            0: 0,        # 0s
            1: 1,        # 1s
            2: 10,       # 10s
            3: 60,       # 60s
            4: 300,      # 300s
            5: 3600,     # 3600s
            6: 21600,    # 6h
            7: 86400     # 24h
        }
        
        # 添加垂直伸展器
        control_layout.addStretch()
        
        # 初始化3D场景
        self.initialize_scene()
    
    def initialize_scene(self):
        """初始化3D场景"""
        # 加载地球模型
        mesh = examples.planets.load_earth()
        
        # 修改地球模型的半径为真实半径（6371公里）
        true_earth_radius = 6371  # 真实地球的平均半径（公里）
        # 缩放地球模型
        mesh.points *= true_earth_radius
        
        pi_matrix = np.array([
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, 1]
        ])
        
        # 应用旋转矩阵到地球模型
        rotated_points = []
        for point in mesh.points:
            # 应用旋转矩阵
            rotated_point = pi_matrix @ point
            rotated_points.append(rotated_point)
        
        # 更新地球模型的点
        mesh.points = np.array(rotated_points)
        
        # 加载地球纹理
        texture = examples.load_globe_texture()
        
        # 添加地球模型到场景中
        self.earth_mesh = mesh
        # 保存地球的初始状态
        self.earth_initial_points = self.earth_mesh.points.copy()
        self.plotter_widget.add_mesh(self.earth_mesh, texture=texture, name='earth')
        
        # 添加星空模型（第一层：星空背景）
        mesh_sky = examples.planets.load_earth()
        mesh_sky.points *= 1000000
        
        # 加载星空纹理
        texture_sky = pv.Texture('textures/starmap_8k_flipped.jpg')
        
        # 添加星空模型到场景中
        self.plotter_widget.add_mesh(mesh_sky, texture=texture_sky, name='sky')
        
        # 添加星座连线图（第二层）
        mesh_constellations = examples.planets.load_earth()
        mesh_constellations.points *= 1000000  # 稍微大一点，确保在星空背景之上
        mesh_constellations.flip_faces()
        
        # 加载星座连线纹理
        texture_constellations = pv.Texture('textures/constellation_figures_flipped.jpg')
        
        # 添加星座连线模型到场景中
        self.constellation_mesh = self.plotter_widget.add_mesh(mesh_constellations, texture=texture_constellations, name='constellations', opacity=0.2)
        
        # 添加日月和行星
        self.add_solar_system()
        
        # 添加天球网格线
        self.add_sky_grid()
        
        # 添加主要恒星到天球上
        self.add_main_stars()
        
        # 保存恒星对象的引用，以便后续控制其可见性
        self.stars_cloud = None
        self.star_labels = []
        
        # 设置相机位置
        cam_pos = (0, -50000, 25000)
        focal_point = (0, 0, 0)
        view_up = (0, 0, 1)
        self.plotter_widget.camera_position = (cam_pos, focal_point, view_up)
        
        # 启用地形交互模式（保持 view_up 固定）
        self.plotter_widget.enable_terrain_style()
        
        # 在每次渲染后保存相机位置
        # 注意：这里我们不使用回调，而是在update_earth_rotation方法中直接使用当前相机位置
        # 这样可以避免QtInteractor没有add_callback方法的问题
        
        # 添加坐标轴，设置标签颜色为白色
        self.plotter_widget.add_axes(xlabel='X', ylabel='Y', zlabel='Z', color='white')
        
        # 更新地球自转的初始位置
        self.update_earth_rotation()
        
        # 渲染场景
        self.plotter_widget.render()
    
    def add_sky_grid(self):
        """在天球上添加网格线"""
        # 天球半径
        sky_radius = 1000000-500  # 与星空模型的半径相同
        
        # 创建经纬网格线
        # 经度线（垂直方向）
        longitude_lines = []
        num_longitudes = 36  # 经度线数量
        for i in range(num_longitudes):
            # 计算经度角度（弧度）
            lon = (i / num_longitudes) * 2 * np.pi
            
            # 创建经度线上的点
            points = []
            num_points = 100  # 每条线上的点数量
            for j in range(num_points):
                # 计算纬度角度（弧度）
                lat = (-np.pi/2) + (j / (num_points-1)) * np.pi
                
                # 计算3D坐标
                x = sky_radius * np.cos(lat) * np.cos(lon)
                y = sky_radius * np.cos(lat) * np.sin(lon)
                z = sky_radius * np.sin(lat)
                
                points.append([x, y, z])
            
            # 创建经度线
            line = pv.lines_from_points(points)
            longitude_lines.append(line)
        
        # 纬度线（水平方向）
        latitude_lines = []
        num_latitudes = 18  # 纬度线数量
        for i in range(1, num_latitudes):
            # 计算纬度角度（弧度）
            lat = (-np.pi/2) + (i / num_latitudes) * np.pi
            
            # 创建纬度线上的点
            points = []
            num_points = 100  # 每条线上的点数量
            for j in range(num_points):
                # 计算经度角度（弧度）
                lon = (j / (num_points-1)) * 2 * np.pi
                
                # 计算3D坐标
                x = sky_radius * np.cos(lat) * np.cos(lon)
                y = sky_radius * np.cos(lat) * np.sin(lon)
                z = sky_radius * np.sin(lat)
                
                points.append([x, y, z])
            
            # 创建纬度线
            line = pv.lines_from_points(points)
            latitude_lines.append(line)
        
        # 合并所有经纬线
        all_lines = longitude_lines + latitude_lines
        combined_lines = pv.MultiBlock(all_lines)
        
        # 添加网格线到场景中，使用半透明的白色
        self.sky_grid_actor = self.plotter_widget.add_mesh(combined_lines, color='white', opacity=0.5, line_width=1, name='sky_grid')
    
    def toggle_stars(self, state):
        """显示/隐藏恒星的复选框回调函数"""
        # 直接控制恒星演员的可见性
        if hasattr(self, 'stars_actors') and self.stars_actors:
            # 设置所有恒星演员的可见性
            for actor in self.stars_actors:
                if actor:
                    actor.SetVisibility(state)
            
            # 同时控制恒星名称标签的可见性
            for text_actor in self.star_labels:
                if text_actor:
                    text_actor.SetVisibility(state)
            
            # 同时控制星座连线的可见性
            if hasattr(self, 'constellation_lines') and self.constellation_lines:
                for line_actor in self.constellation_lines:
                    if line_actor:
                        line_actor.SetVisibility(state)
        
        # 重新渲染场景
        self.plotter_widget.render()
    
    def toggle_sky_grid(self, state):
        """显示/隐藏天球网格的复选框回调函数"""
        # 直接控制天球网格演员的可见性
        if hasattr(self, 'sky_grid_actor') and self.sky_grid_actor:
            # 设置天球网格演员的可见性
            self.sky_grid_actor.SetVisibility(state)
        
        # 重新渲染场景
        self.plotter_widget.render()
    
    def toggle_constellations(self, state):
        """显示/隐藏星座连线图的复选框回调函数"""
        # 直接控制星座连线图演员的可见性
        if hasattr(self, 'constellation_mesh') and self.constellation_mesh:
            # 设置星座连线图演员的可见性
            self.constellation_mesh.SetVisibility(state)
        
        # 重新渲染场景
        self.plotter_widget.render()
    
    def add_solar_system(self):
        """添加日月和行星到场景中"""
        # 定义要显示的天体
        self.bodies = {
            'sun': {
                'name': '太阳',
                'color': 'yellow', 
                'size': 10000,
                'skyfield_name': 10  # 太阳的ID
            },
            'moon': {
                'name': '月球',
                'color': 'white', 
                'size': 10000,
                'skyfield_name': 301  # 月球的ID
            },
            'mercury': {
                'name': '水星',
                'color': 'white', 
                'size': 2000,
                'skyfield_name': 199  # 水星的ID
            },
            'venus': {
                'name': '金星',
                'color': 'yellow', 
                'size': 3000,
                'skyfield_name': 299  # 金星的ID
            },
            'mars': {
                'name': '火星',
                'color': 'red', 
                'size': 2500,
                'skyfield_name': 499  # 火星的ID
            },
            'jupiter': {
                'name': '木星',
                'color': 'orange', 
                'size': 8000,
                'skyfield_name': 5  # 木星 barycenter的ID
            },
            'saturn': {
                'name': '土星',
                'color': 'yellow', 
                'size': 6000,
                'skyfield_name': 6  # 土星 barycenter的ID
            },
            'uranus': {
                'name': '天王星',
                'color': 'lightblue', 
                'size': 4000,
                'skyfield_name': 7  # 天王星 barycenter的ID
            },
            'neptune': {
                'name': '海王星',
                'color': 'blue', 
                'size': 3500,
                'skyfield_name': 8  # 海王星 barycenter的ID
            }
        }
        
        # 天球半径
        self.sky_radius = 1000000
        
        # 遍历每个天体
        for body_name, body_info in self.bodies.items():
            try:
                # 获取天体
                body = self.planets[body_info['skyfield_name']]
                
                # 获取时间尺度
                t = self.ts.from_datetime(self.simulation_time)
                
                # 计算天体相对于地球的位置
                astrometric = self.earth.at(t).observe(body)
                ra, dec, distance = astrometric.radec()
                
                # 转换为弧度
                ra_rad = ra.radians
                dec_rad = dec.radians
                
                # 计算天球上的3D坐标
                # 使用赤经赤纬计算天球坐标
                x_sky = self.sky_radius * np.cos(dec_rad) * np.cos(ra_rad)
                y_sky = self.sky_radius * np.cos(dec_rad) * np.sin(ra_rad)
                z_sky = self.sky_radius * np.sin(dec_rad)
                
                # 应用地球自转和镜像变换
                pos = np.array([x_sky, y_sky, z_sky])

                # 创建天体模型
                size = body_info['size']
                sphere = pv.Sphere(radius=size, center=pos)
                
                # 添加到场景中
                actor = self.plotter_widget.add_mesh(sphere, color=body_info['color'], name=body_info['name'])
                self.solar_system_actors[body_name] = actor
                
                # 如果是太阳，添加到地心的连线并设置光源
                if body_name == 'sun':
                    # 创建太阳到地心的连线
                    line_points = [pos, [0, 0, 0]]  # 太阳位置到原点（地心）
                    line = pv.lines_from_points(line_points)
                    sun_earth_line = self.plotter_widget.add_mesh(line, color='yellow', line_width=2, name='sun_earth_line')
                    self.solar_system_actors['sun_earth_line'] = sun_earth_line
                    
                    # 在太阳位置设置光源
                    # 保存光源引用，以便后续更新
                    light = pv.Light(position=pos, focal_point=[0, 0, 0], intensity=1.0, color='white')
                    self.plotter_widget.add_light(light)
                    self.solar_system_actors['sun_light'] = light
                
                # 转换为时分秒格式
                ra_str = ra.hms()
                dec_str = dec.dms()
                
                # 格式化输出
                ra_hms_str = f"{int(ra_str[0])}h {int(ra_str[1])}m {ra_str[2]:.1f}s"
                dec_dms_str = f"{int(dec_str[0])}° {int(abs(dec_str[1]))}' {abs(dec_str[2]):.1f}\""
                if dec_str[0] < 0:
                    dec_dms_str = f"-{dec_dms_str}"
                
                # 添加标签，包含赤经赤纬信息
                label_text = f"{body_info['name']}\nRA: {ra_hms_str}\nDec: {dec_dms_str}"
                text_actor = self.plotter_widget.add_text(label_text, position=pos, font_size=8, color=body_info['color'])
                self.solar_system_actors[f'{body_name}_label'] = text_actor
                
                print(f"添加天体: {body_info['name']}，位置: {pos}")
                print(f"  赤经: {ra_hms_str}，赤纬: {dec_dms_str}")
                print(f"  距离: {distance.au:.6f} AU")
                
            except Exception as e:
                print(f"添加天体 {body_info['name']} 失败: {e}")
                continue
        
        # 标记为使用了真实位置
        use_real_positions = True
    
    def toggle_solar_system(self, state):
        """显示/隐藏日月和行星的复选框回调函数"""
        # 直接控制日月和行星演员的可见性
        if hasattr(self, 'solar_system_actors') and self.solar_system_actors:
            # 设置所有日月和行星演员的可见性
            for actor_name, actor in self.solar_system_actors.items():
                if actor:
                    actor.SetVisibility(state)
        
        # 重新渲染场景
        self.plotter_widget.render()
    
    def toggle_earth_rotation(self, state):
        """地球自转控制复选框回调函数"""
        # 重新渲染场景
        self.plotter_widget.render()
    
    def slider_callback(self, value):
        """滑块回调函数"""
        # 获取映射后的步长值
        step_seconds = self.step_mapping.get(value, 0)
        
        # 格式化步长显示
        if step_seconds == 0:
            step_str = "0s"
        elif abs(step_seconds) == 1:
            step_str = f"{step_seconds}s"
        elif abs(step_seconds) == 10:
            step_str = f"{step_seconds}s"
        elif abs(step_seconds) == 60:
            step_str = f"{step_seconds}s"
        elif abs(step_seconds) == 300:
            step_str = f"{step_seconds}s"
        elif abs(step_seconds) == 3600:
            step_str = f"{step_seconds}s"
        elif abs(step_seconds) == 21600:
            step_str = f"{step_seconds//3600}h"
        elif abs(step_seconds) == 86400:
            step_str = f"{step_seconds//3600}h"
        else:
            step_str = f"{step_seconds}s"
        
        print(f"步长值: {step_str}")
        self.slider_value_label.setText(f"步长值: {step_str}")
    
    def run_simulation(self):
        """运行仿真"""
        print("开始运行仿真...")
        self.simulation_running = True
        
        # 如果还没有定时器，创建一个
        if self.timer is None:
            from PyQt5.QtCore import QTimer
            self.timer = QTimer()
            self.timer.timeout.connect(self.simulation_step_callback)
            self.timer.start(100)  # 每100毫秒执行一次
        else:
            self.timer.start(100)
    
    def pause_simulation(self):
        """暂停仿真"""
        print("暂停仿真...")
        self.simulation_running = False
        
        # 停止定时器
        if self.timer:
            self.timer.stop()
    
    def simulation_step_callback(self):
        """仿真步长回调函数"""
        if not self.simulation_running:
            return
        
        # 根据滑块值获取映射后的仿真步长
        slider_value = self.slider.value()
        step_seconds = self.step_mapping.get(slider_value, 0)
        
        # 更新仿真时间
        self.simulation_time += datetime.timedelta(seconds=step_seconds)
        
        # 更新时间显示
        self.time_display_label.setText(self.simulation_time.strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        # 更新日月和行星位置
        self.update_solar_system()
        
        # 更新地球自转
        self.update_earth_rotation()
        
        # 重新渲染场景
        self.plotter_widget.render()
    
    def update_earth_rotation(self):
        """更新地球模型的旋转"""
        # 获取时间尺度
        t = self.ts.from_datetime(self.simulation_time)
        
        # 使用skyfield库计算GMST（返回小时）
        gmst_hours = t.gmst
        
        # 将小时转换为弧度（1小时 = 2π/24 弧度）
        gmst_rad = gmst_hours * (2 * np.pi / 24)
        
        # 计算地球自转角度
        # 注意：这里我们使用GMST来计算地球的旋转角度
        # 因为GMST表示的是格林威治子午线的恒星时，与地球自转直接相关
        rotation_angle = gmst_rad
        
        # 应用旋转到地球模型
        if hasattr(self, 'earth_mesh') and self.earth_mesh:
            # 创建旋转矩阵（绕z轴旋转）
            rotation_matrix = np.array([
                [np.cos(rotation_angle), -np.sin(rotation_angle), 0],
                [np.sin(rotation_angle), np.cos(rotation_angle), 0],
                [0, 0, 1]
            ])
            
            # 应用旋转（从初始状态开始）
            # 假设地球的中心在原点，直接应用旋转矩阵
            rotated_points = []
            for point in self.earth_initial_points:
                # 直接应用旋转矩阵
                rotated_point = rotation_matrix @ point
                rotated_points.append(rotated_point)
            
            # 更新地球模型的点
            self.earth_mesh.points = np.array(rotated_points)
        
        # 根据checkbox状态决定是否旋转相机
        if hasattr(self, 'earth_rotation_checkbox'):
            # 获取checkbox状态
            earth_rotation_only = self.earth_rotation_checkbox.isChecked()
            
            # 如果不选地球自转（即相机随地球一起自转）
            if not earth_rotation_only:
                # 获取当前相机位置
                current_camera = self.plotter_widget.camera_position
                if current_camera:
                    cam_pos, focal_point, view_up = current_camera
                    
                    # 计算GMST的差值
                    if self.last_gmst_rad is not None:
                        # 使用差值作为旋转角度
                        delta_gmst_rad = gmst_rad - self.last_gmst_rad
                    else:
                        # 第一次运行，使用0作为旋转角度
                        delta_gmst_rad = 0
                    
                    # 将相机位置转换为numpy数组
                    cam_pos_np = np.array(cam_pos)
                    
                    # 创建旋转矩阵（绕z轴旋转）
                    # 注意：这里我们使用负的旋转角度，因为相机需要与地球自转方向相反才能保持相对静止
                    camera_rotation_matrix = np.array([
                        [np.cos(delta_gmst_rad), -np.sin(delta_gmst_rad), 0],
                        [np.sin(delta_gmst_rad), np.cos(delta_gmst_rad), 0],
                        [0, 0, 1]
                    ])
                    
                    # 应用旋转到相机位置
                    rotated_cam_pos = camera_rotation_matrix @ cam_pos_np
                    
                    # 更新相机位置
                    self.plotter_widget.camera_position = (tuple(rotated_cam_pos), focal_point, view_up)
        
        # 更新last_gmst_rad为当前值
        self.last_gmst_rad = gmst_rad
    
    def update_solar_system(self):
        """更新日月和行星位置"""
        
        # 获取时间尺度
        t = self.ts.from_datetime(self.simulation_time)
        
        # 遍历每个天体
        for body_name, body_info in self.bodies.items():
            try:
                # 获取天体
                body = self.planets[body_info['skyfield_name']]
                
                # 计算天体相对于地球的位置
                astrometric = self.earth.at(t).observe(body)
                ra, dec, distance = astrometric.radec()
                
                # 转换为弧度
                ra_rad = ra.radians
                dec_rad = dec.radians
                
                # 计算天球上的3D坐标
                x_sky = self.sky_radius * np.cos(dec_rad) * np.cos(ra_rad)
                y_sky = self.sky_radius * np.cos(dec_rad) * np.sin(ra_rad)
                z_sky = self.sky_radius * np.sin(dec_rad)
                
                # 应用地球自转和镜像变换
                pos = np.array([x_sky, y_sky, z_sky])

                # 更新天体位置
                if body_name in self.solar_system_actors:
                    actor = self.solar_system_actors[body_name]
                    if actor:
                        # 获取球体网格
                        mesh = actor.GetMapper().GetInput()
                        # 更新球体位置
                        mesh.points = mesh.points - mesh.center + pos
                
                # 如果是太阳，更新到地心的连线和光源位置
                if body_name == 'sun':
                    # 更新太阳到地心的连线
                    if 'sun_earth_line' in self.solar_system_actors:
                        line_actor = self.solar_system_actors['sun_earth_line']
                        if line_actor:
                            line_mesh = line_actor.GetMapper().GetInput()
                            line_points = [pos, [0, 0, 0]]  # 太阳位置到原点（地心）
                            new_line = pv.lines_from_points(line_points)
                            line_mesh.points = new_line.points
                    
                    # 更新光源位置
                    if 'sun_light' in self.solar_system_actors:
                        light = self.solar_system_actors['sun_light']
                        if light:
                            # 更新光源位置
                            light.SetPosition(pos[0], pos[1], pos[2])
                        
                # 更新标签位置
                label_name = f'{body_name}_label'
                if label_name in self.solar_system_actors:
                    text_actor = self.solar_system_actors[label_name]
                    if text_actor:
                        # 更新标签位置（使用PyVista的方法）
                        text_actor.position = pos
                        
                        # 更新标签内容
                        # 转换为时分秒格式
                        ra_str = ra.hms()
                        dec_str = dec.dms()
                        
                        # 格式化输出
                        ra_hms_str = f"{int(ra_str[0])}h {int(ra_str[1])}m {ra_str[2]:.1f}s"
                        dec_dms_str = f"{int(dec_str[0])}° {int(abs(dec_str[1]))}' {abs(dec_str[2]):.1f}\""
                        if dec_str[0] < 0:
                            dec_dms_str = f"-{dec_dms_str}"
                        
                        # 更新标签文本
                        label_text = f"{body_info['name']}\nRA: {ra_hms_str}\nDec: {dec_dms_str}"
                        # 移除旧标签并添加新标签
                        self.plotter_widget.remove_actor(text_actor)
                        new_text_actor = self.plotter_widget.add_text(label_text, position=pos, font_size=8, color=body_info['color'])
                        self.solar_system_actors[label_name] = new_text_actor
                
            except Exception as e:
                print(f"更新天体 {body_info['name']} 失败: {e}")
                continue
    
    def read_constellations(self, file_path):
        """读取星座数据文件"""
        constellations = {}
        current_constellation = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # 检查是否是星座标题行
                if '主要恒星坐标:' in line:
                    # 提取星座名称
                    constellation_name = line.split('主要恒星坐标:')[0].strip()
                    current_constellation = constellation_name
                    constellations[current_constellation] = []
                else:
                    # 解析恒星数据
                    if current_constellation:
                        # 使用正则表达式解析恒星数据
                        pattern = r'(.+?)\s+\((.+?)\):\s+视星等\s+([\d.-]+),\s+赤经\s+(.+?),\s+赤纬\s+(.+?),\s+光谱型\s+(.+)'
                        match = re.match(pattern, line)
                        
                        if match:
                            star_id, star_name, magnitude, ra_str, dec_str, spectral_type = match.groups()
                        else:
                            # 尝试简化格式
                            parts = line.split('): 视星等 ')
                            if len(parts) == 2:
                                star_part = parts[0]
                                rest_part = parts[1]
                                
                                # 提取恒星ID和名称
                                star_id_name = star_part.split(' ')
                                star_id = star_id_name[0]
                                if len(star_id_name) > 1:
                                    star_name = ' '.join(star_id_name[1:])
                                else:
                                    star_name = star_id
                                
                                # 提取视星等、赤经、赤纬、光谱型
                                rest_parts = rest_part.split(', 赤经 ')
                                if len(rest_parts) == 2:
                                    magnitude = rest_parts[0]
                                    ra_dec_spec = rest_parts[1].split(', 赤纬 ')
                                    if len(ra_dec_spec) == 2:
                                        ra_str = ra_dec_spec[0]
                                        dec_spec = ra_dec_spec[1].split(', 光谱型 ')
                                        if len(dec_spec) == 2:
                                            dec_str = dec_spec[0]
                                            spectral_type = dec_spec[1]
                                        else:
                                            dec_str = dec_spec[0]
                                            spectral_type = ''
                                    else:
                                        ra_str = ra_dec_spec[0]
                                        dec_str = ''
                                        spectral_type = ''
                                else:
                                    magnitude = rest_parts[0]
                                    ra_str = ''
                                    dec_str = ''
                                    spectral_type = ''
                            else:
                                # 最简单的格式
                                parts = line.split(': 视星等 ')
                                if len(parts) == 2:
                                    star_info = parts[0]
                                    rest_info = parts[1]
                                    
                                    # 提取恒星ID和名称
                                    star_parts = star_info.split(' ')
                                    star_id = star_parts[0]
                                    star_name = ' '.join(star_parts[1:]) if len(star_parts) > 1 else star_id
                                    
                                    # 提取其他信息
                                    info_parts = rest_info.split(', ')
                                    if len(info_parts) >= 4:
                                        magnitude = info_parts[0]
                                        ra_str = info_parts[1].replace('赤经 ', '')
                                        dec_str = info_parts[2].replace('赤纬 ', '')
                                        spectral_type = info_parts[3].replace('光谱型 ', '')
                                    else:
                                        magnitude = info_parts[0]
                                        ra_str = ''
                                        dec_str = ''
                                        spectral_type = ''
                                else:
                                    continue
                        
                        # 转换赤经赤纬为数值
                        try:
                            # 解析赤经
                            # 尝试从括号中提取度数
                            ra_match = re.search(r'\(([\d.-]+)°\)', ra_str)
                            if ra_match:
                                # 直接使用括号中的度数
                                ra_deg = float(ra_match.group(1))
                            else:
                                # 尝试解析时:分格式
                                ra_parts = ra_str.split('h ')
                                if len(ra_parts) == 2:
                                    ra_hour = float(ra_parts[0])
                                    ra_min_part = ra_parts[1].split('m')[0]
                                    ra_min = float(ra_min_part)
                                    ra_deg = (ra_hour + ra_min/60) * 15  # 1小时 = 15度
                                else:
                                    # 直接是度数
                                    ra_deg = float(ra_str.replace('°', ''))
                            
                            # 解析赤纬
                            # 尝试从括号中提取度数
                            dec_match = re.search(r'\(([\d.-]+)°\)', dec_str)
                            if dec_match:
                                # 直接使用括号中的度数
                                dec_deg = float(dec_match.group(1))
                            else:
                                # 尝试解析度:分格式
                                dec_parts = dec_str.split('° ')
                                if len(dec_parts) == 2:
                                    dec_deg = float(dec_parts[0])
                                    dec_min_part = dec_parts[1].split("'")[0]
                                    dec_min = float(dec_min_part)
                                    if dec_deg < 0:
                                        dec_deg = dec_deg - dec_min/60
                                    else:
                                        dec_deg = dec_deg + dec_min/60
                                else:
                                    # 直接是度数
                                    dec_deg = float(dec_str.replace('°', ''))
                            
                            # 转换为弧度
                            ra_rad = np.radians(ra_deg)#(360 - (ra_deg+180)%360)
                            dec_rad = np.radians(dec_deg)
                            
                            # 计算三维坐标
                            # 假设距离为1（天球）
                            distance = 1.0
                            x = distance * np.cos(dec_rad) * np.cos(ra_rad)
                            y = distance * np.cos(dec_rad) * np.sin(ra_rad)
                            z = distance * np.sin(dec_rad)
                            
                            # 添加恒星数据
                            constellations[current_constellation].append({
                                'id': star_id,
                                'name': star_name,
                                'magnitude': float(magnitude),
                                'ra_deg': ra_deg,
                                'dec_deg': dec_deg,
                                'ra_rad': ra_rad,
                                'dec_rad': dec_rad,
                                'spectral_type': spectral_type,
                                'x': x,
                                'y': y,
                                'z': z
                            })
                        except Exception as e:
                            print(f"解析恒星数据失败: {line}, 错误: {e}")
                            continue
        
        return constellations
    
    def add_main_stars(self):
        """在天球上添加主要恒星"""
        # 读取星座数据
        constellations = self.read_constellations('stars.txt')
        
        # 定义星座颜色映射
        constellation_colors = {
            '猎户座': 'red',
            '摩羯座': 'green',
            '天鹰座': 'blue',
            '天琴座': 'cyan',
            '天鹅座': 'magenta',
            '大熊座': 'yellow',
            '牧夫座': 'orange',
            '狮子座': 'purple',
            '双子座': 'pink',
            '仙女座': 'lightgreen',
            '飞马座': 'lightblue'
        }
        
        # 定义星座连线数据
        constellation_connections = {
            '猎户座': [
                [0, 2],
                [2, 6],
                [4, 5],
                [5, 6],
                [6, 1],
                [1, 3],
                [3, 4],
                [4, 0]
            ],
            '摩羯座': [
                [2, 1],
                [1, 5],
                [5, 8],
                [8, 3],
                [3, 0],
                [0, 4],
                [4, 9],
                [9, 6],
                [6, 7],
                [7, 1]
            ],
            '牧夫座': [
                [0, 1],
                [1, 4],
                [4, 5],
                [5, 3],
                [3, 6],
                [6, 0],
                [0, 2],
                [0, 7]
            ],
            '狮子座': [
                [0, 7],
                [7, 1],
                [1, 6],
                [6, 8],
                [8, 4],
                [1, 3],
                [3, 2],
                [2, 5],
                [5, 0]
            ],
            '双子座': [
                [1, 13],
                [0, 11],
                [11, 7],
                [11, 9],
                [9, 13],
                [13, 8],
                [13, 4],
                [4, 12],
                [4, 3],
                [11, 6],
                [6, 10],
                [10, 5],
                [10, 2]
            ],
            '仙女座_飞马座联合': [
                [2, 1],
                [1, 3],
                [3, 0],
                [4, 10],
                [10, 9],
                [9, 6],
                [6, 7],
                [7, 0],
                [0, 5],
                [5, 8],
                [5, 6]
            ]
        }
        
        # 天球半径
        sky_radius = 1000000 - 500  # 与星空模型的半径相同
        
        # 保存恒星演员、标签和连线
        self.stars_actors = []
        self.star_labels = []
        self.constellation_lines = []
        
        # 特殊处理：联合仙女座和飞马座
        combined_stars = []
        combined_positions = []
        andromeda_stars = constellations.get('仙女座', [])
        pegasus_stars = constellations.get('飞马座', [])
        
        if andromeda_stars or pegasus_stars:
            # 收集仙女座恒星
            for star in andromeda_stars:
                scale = sky_radius
                pos = (star['x'] * scale, star['y'] * scale, star['z'] * scale)
                combined_stars.append(star)
                combined_positions.append(pos)
                
                # 添加恒星（球体）
                size = max(5, 20 - star['magnitude'] * 2)
                sphere = pv.Sphere(radius=size, center=pos)
                actor = self.plotter_widget.add_mesh(sphere, color='lightgreen', name=star['name'])
                self.stars_actors.append(actor)
                
                # 添加标签
                text_actor = self.plotter_widget.add_text(star['name'], position=pos, font_size=8, color='lightgreen', name=f'star_label_{star['name']}')
                self.star_labels.append(text_actor)
            
            # 收集飞马座恒星
            for star in pegasus_stars:
                scale = sky_radius
                pos = (star['x'] * scale, star['y'] * scale, star['z'] * scale)
                combined_stars.append(star)
                combined_positions.append(pos)
                
                # 添加恒星（球体）
                size = max(5, 20 - star['magnitude'] * 2)
                sphere = pv.Sphere(radius=size, center=pos)
                actor = self.plotter_widget.add_mesh(sphere, color='lightblue', name=star['name'])
                self.stars_actors.append(actor)
                
                # 添加标签
                text_actor = self.plotter_widget.add_text(star['name'], position=pos, font_size=8, color='lightblue', name=f'star_label_{star['name']}')
                self.star_labels.append(text_actor)
            
            # 绘制仙女座和飞马座的联合连线
            if len(combined_positions) > 1:
                connections = constellation_connections.get('仙女座_飞马座联合', [])
                if connections:
                    all_lines = []
                    for connection in connections:
                        if len(connection) == 2:
                            idx1, idx2 = connection
                            if 0 <= idx1 < len(combined_positions) and 0 <= idx2 < len(combined_positions):
                                all_lines.extend([2, idx1, idx2])
                    
                    if all_lines:
                        poly_data = pv.PolyData(combined_positions)
                        poly_data.lines = all_lines
                        actor = self.plotter_widget.add_mesh(poly_data, color='white', line_width=2, name='仙女座_飞马座联合_line')
                        self.constellation_lines.append(actor)
            
            print(f"加载联合星座: 仙女座_飞马座, 恒星数量: {len(combined_stars)}")
        
        # 遍历其他星座
        for constellation_name, stars in constellations.items():
            # 跳过已经处理过的星座
            if constellation_name in ['仙女座', '飞马座']:
                continue
            
            if not stars:
                continue
            
            # 确定星座颜色
            color = constellation_colors.get(constellation_name, 'white')
            
            # 收集恒星位置
            star_positions = []
            
            for star in stars:
                scale = sky_radius
                pos = (star['x'] * scale, star['y'] * scale, star['z'] * scale)
                star_positions.append(pos)
                
                # 添加恒星（球体）
                size = max(5, 20 - star['magnitude'] * 2)
                sphere = pv.Sphere(radius=size, center=pos)
                actor = self.plotter_widget.add_mesh(sphere, color=color, name=star['name'])
                self.stars_actors.append(actor)
                
                # 添加标签
                text_actor = self.plotter_widget.add_text(star['name'], position=pos, font_size=8, color=color, name=f'star_label_{star['name']}')
                self.star_labels.append(text_actor)
            
            # 连接恒星形成星座轮廓
            if len(star_positions) > 1:
                # 检查是否有预设的连线数据
                connections = constellation_connections.get(constellation_name, [])
                
                if connections:
                    # 使用预设的连线数据
                    all_lines = []
                    for connection in connections:
                        if len(connection) == 2:
                            idx1, idx2 = connection
                            if 0 <= idx1 < len(star_positions) and 0 <= idx2 < len(star_positions):
                                # 添加线段
                                all_lines.extend([2, idx1, idx2])
                    
                    if all_lines:
                        # 创建折线
                        poly_data = pv.PolyData(star_positions)
                        poly_data.lines = all_lines
                        actor = self.plotter_widget.add_mesh(poly_data, color=color, line_width=2, name=f"{constellation_name}_line")
                        self.constellation_lines.append(actor)
                        print(f"使用预设连线数据绘制 {constellation_name} 星座")
                else:
                    # 默认连接所有恒星
                    poly_data = pv.PolyData(star_positions)
                    lines = [len(star_positions)] + list(range(len(star_positions)))
                    poly_data.lines = lines
                    actor = self.plotter_widget.add_mesh(poly_data, color=color, line_width=2, name=f"{constellation_name}_line")
                    self.constellation_lines.append(actor)
            
            print(f"加载星座: {constellation_name}, 恒星数量: {len(stars)}")

if __name__ == "__main__":
    # 创建应用程序
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = SatelliteOrbitApp()
    
    # 显示主窗口
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())
