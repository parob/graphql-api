import io

from setuptools import setup, find_packages

with io.open('README.md', 'rt', encoding='utf8') as readme_file:
    readme = readme_file.read()

with io.open('VERSION') as version_file:
    version = version_file.read().strip().lower()
    if version.startswith("v"):
        version = version[1:]

setup(
    name='objectql',
    version=version,
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    author='Robert Parker',
    author_email='rob@parob.com',
    url='https://objectql.com',
    download_url=f'https://gitlab.com/kiwi-ninja/objectql/-/archive/v{version}/objectql-v{version}.tar.gz',
    keywords=['GraphQL', 'ObjectQL', 'Server'],
    description='A framework for building Python GraphQL servers.',
    long_description=readme,
    long_description_content_type='text/markdown',
    install_requires=[
        'graphql-core >= 3.0.0',
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
