import io

from setuptools import setup, find_packages

with io.open('README.md', 'rt', encoding='utf8') as f:
    readme = f.read()

setup(
    name='objectql',
    version='0.1',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    author='Robert Parker',
    author_email='rob@parob.com',
    url = 'https://github.com/user/reponame',
    download_url = 'https://github.com/user/reponame/archive/v_01.tar.gz',
    keywords = ['GraphQL', 'ObjectQL', 'Server'], 
    description='A framework for building Python GraphQL servers.',
    long_description=readme,
    install_requires=[
        'graphql-core',
        'requests',
        'typing-inspect'
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-cov',
            'coverage',
            'faker'
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
