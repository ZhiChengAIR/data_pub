from setuptools import find_packages, setup

package_name = 'data_pub'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
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
        ],
    },
)