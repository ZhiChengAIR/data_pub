from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'data_pub'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools','pyserial'],
    zip_safe=True,
    maintainer='h666',
    maintainer_email='zc@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest','pyserial'],
     entry_points={
        'console_scripts': [
            'pub=data_pub.data_pub:main',
            # Camera publishers
            'cam_high_pub = data_pub.cam_pub:main',
            'cam_wrist_left_pub = data_pub.cam_pub:main',
            'cam_low_pub = data_pub.cam_pub:main',
            'cam_wrist_right_pub = data_pub.cam_pub:main',
            # Arm publishers
            'arm_left_pub = data_pub.data_pub:main',
            'arm_right_pub = data_pub.data_pub:main',
        ],
    },
)
