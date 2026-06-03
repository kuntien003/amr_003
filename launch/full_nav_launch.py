import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import ExecuteProcess

cleanup = ExecuteProcess(
    cmd=['bash', '-c', 'killall -9 gzserver gzclient 2>/dev/null; sleep 1'],
    output='screen'
)

def generate_launch_description():

    package_name = 'amr_003'
    pkg_share = get_package_share_directory(package_name)

    # ─── Launch Arguments ───────────────────────────────────────────────────
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation clock')

    # ─── 1. Robot State Publisher ────────────────────────────────────────────
    rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_share, 'launch', 'rsp.launch.py')),
        launch_arguments={
            'use_sim_time': 'true',
            'use_ros2_control': 'true'
        }.items()
    )

    # ─── 2. Joystick ─────────────────────────────────────────────────────────
    joystick = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_share, 'launch', 'joystick.launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items()
    )

    # ─── 3. Twist Mux ────────────────────────────────────────────────────────
    twist_mux_params = os.path.join(pkg_share, 'config', 'twist_mux.yaml')
    twist_mux = Node(
        package='twist_mux',
        executable='twist_mux',
        parameters=[twist_mux_params, {'use_sim_time': True}],
        remappings=[('/cmd_vel_out', '/diff_cont/cmd_vel_unstamped')]
    )

    # ─── 4. Gazebo ───────────────────────────────────────────────────────────
    gazebo_params_file = os.path.join(pkg_share, 'config', 'gazebo_params.yaml')
    world_path = os.path.join(pkg_share, 'worlds', 'myworld.world')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('gazebo_ros'),
                         'launch', 'gazebo.launch.py')),
        launch_arguments={
            'world': world_path,
            'extra_gazebo_args': '--ros-args --params-file ' + gazebo_params_file
        }.items()
    )

    # ─── 5. Spawn Robot ──────────────────────────────────────────────────────
    spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'my_bot_2'],
        output='screen'
    )

    # ─── 6. Controllers ──────────────────────────────────────────────────────
    diff_drive_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_cont'],
    )

    joint_broad_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_broad'],
    )

    # ─── 7. Odom Relay (delay 3s chờ controller khởi động xong) ─────────────
    odom_relay = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='topic_tools',
                executable='relay',
                name='odom_relay',
                parameters=[{'use_sim_time': True}],
                arguments=['/diff_cont/odom', '/odom'],
                output='screen',
            )
        ]
    )

    # ─── 8. SLAM Toolbox (delay 5s chờ Gazebo + robot sẵn sàng) ─────────────
    slam_params = os.path.join(pkg_share, 'config', 'mapper_params_online_async.yaml')

    slam_toolbox = TimerAction(
        period=5.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory('slam_toolbox'),
                        'launch', 'online_async_launch.py')),
                launch_arguments={
                    'slam_params_file': slam_params,
                    'use_sim_time': 'true'
                }.items()
            )
        ]
    )

    # ─── 9. Nav2 (delay 8s chờ SLAM publish map) ─────────────────────────────
    nav2_params = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    navigation = TimerAction(
        period=8.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_share, 'launch', 'navigation_launch.py')),
                launch_arguments={
                    'use_sim_time': 'true',
                    'params_file': nav2_params,
                }.items()
            )
        ]
    )

    # ─── 10. RViz (delay 10s chờ tất cả sẵn sàng) ───────────────────────────
    rviz_config = os.path.join(pkg_share, 'config', 'myrviz2.rviz')

    rviz = TimerAction(
        period=10.0,
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                arguments=['-d', rviz_config],
                parameters=[{'use_sim_time': True}],
                output='screen',
            )
        ]
    )

    return LaunchDescription([
        declare_use_sim_time,
        # Khởi động ngay
        rsp,
        joystick,
        twist_mux,
        gazebo,
        spawn_entity,
        diff_drive_spawner,
        joint_broad_spawner,
        # Delay theo thứ tự
        odom_relay,    # sau 3s
        slam_toolbox,  # sau 5s
        navigation,    # sau 8s
        rviz,          # sau 10s
    ])
