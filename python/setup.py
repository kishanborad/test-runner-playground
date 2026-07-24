from setuptools import setup, find_packages

setup(
    name='test-runner-engine',
    version='1.0.0',
    description='Python test automation engine with report generation and accessibility checking',
    author='Kishan Borad',
    packages=find_packages(),
    install_requires=[
        'beautifulsoup4>=4.12.0',
        'requests>=2.31.0',
        'jinja2>=3.1.0',
        'lxml>=5.0.0',
    ],
    entry_points={
        'console_scripts': [
            'tr-run=test_runner:main',
            'tr-generate=test_generator:main',
            'tr-report=report_builder:main',
            'tr-a11y=accessibility_checker:main',
            'tr-perf=performance_monitor:main',
        ],
    },
    python_requires='>=3.9',
)
