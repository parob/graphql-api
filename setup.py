import io

from setuptools import setup, find_packages

with io.open('README.md', 'rt', encoding='utf8') as f:
    readme = f.read()

setup(
    name='objectql',
    version='0.2',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    author='Robert Parker',
    author_email='rob@parob.com',
    url='https://objectql.com',
    download_url='https://gitlab.com/kiwi-ninja/objectql/-/archive/v0.2/objectql-v0.2.tar.gz',
    keywords=['GraphQL', 'ObjectQL', 'Server'],
    description='A framework for building Python GraphQL servers.',
    long_description=readme,
    long_description_content_type='text/markdown',
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
