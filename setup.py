import io

from setuptools import setup, find_packages

with io.open('README.md', 'rt', encoding='utf8') as readme_file:
    readme = readme_file.read()

with io.open('VERSION') as version_file:
    version = version_file.read().strip().lower()
    if version.startswith("v"):
        version = version[1:]

setup(
    name='graphql-api',
    version=version,
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    author='Robert Parker',
    author_email='rob@parob.com',
    url='https://gitlab.com/parob/graphql-api',
    download_url=f'https://gitlab.com/parob/graphql/-/archive/v{version}/graphql-api-v{version}.tar.gz',
    keywords=['GraphQL', 'GraphQL-API', 'GraphQLAPI', 'Server'],
    description='A framework for building Python GraphQL APIs.',
    long_description=readme,
    long_description_content_type='text/markdown',
    install_requires=[
        'graphql-core>=3.1.2',
        'requests>=2.24.0',
        'typing-inspect>=0.6.0',
        'aiohttp>=3.8.0'
    ],
    extras_require={
        'dev': [
            'pytest>=5.4.3',
            'pytest-cov>=2.10.0',
            'coverage>=5.2',
            'faker>=4.1.1'
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
