from setuptools import setup, find_packages

def readme():
    with open('README.md') as f:
        return f.read()


version = '0.0.187.dev0'

setup(
    name='insanic',
    version=version,
    description='API framework for sanic',
    long_description=readme(),
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Application Frameworks'
    ],
    keywords='api framework sanic async asyncio microservice msa',
    url='http://github.com/MyMusicTaste/insanic',
    author='crazytruth',
    author_email='kwangjinkim@gmail.com',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    setup_requires=["zest.releaser[recommended]", "setuptools"],
    install_requires=[
        'sanic==0.7.0',
        'sanic-useragent',
        'aiohttp<=2.3.0',
        'aiodns',
        'aioredis>=0.3.0,<1.0.0',
        'PyJWT',
        'aws-xray-sdk'
    ],
    # test_suite='nose.collector',
    tests_require=['pytest', ],
    entry_points={
        'pytest11': [
            'insanic = insanic.testing.pytest_plugin',
        ]
    },
    extras_require={
        "testing":  ["docker", "aiobotocore", "pytest", "pytest-asyncio", "pytest-redis"],
        "dev": ["zest.releaser[recommended]", "flake8"]
    },

    include_package_data=True,
    zip_safe=False
)

