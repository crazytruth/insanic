from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()

def version():
    with open('VERSION') as f:
        return f.read().strip()

setup(
    name='insanic',
    version=version(),
    description='API framework for sanic',
    long_description=readme(),
    classifiers=[
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.6',
    ],
    keywords='api framework sanic async',
    url='http://github.com/',
    author='crazytruth',
    author_email='kwangjinkim@gmail.com',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=[
        'sanic',
        'sanic-useragent',
        'aiohttp',
        'aiomysql',
        'aioredis',
        'cryptography',
        'peewee-async',
        'PyJWT',
        'marshmallow',
        'Marshmallow-Peewee',
        'docker',
        'boto3'
    ],
    # test_suite='nose.collector',
    # tests_require=['nose', 'nose-cover3'],
    # entry_points={
    #     'console_scripts': [''],
    # },
    include_package_data=True,
    zip_safe=False
)

