from setuptools import setup

setup(
    name='mytracker_export_api',
    version='1.0.0',
    description='Python wrapper for MyTracker Export API.',
    packages=['mytracker_export_api'],
    author='Artyom Novopolsky',
    author_email='a.novopolsky@corp.mail.ru',
    install_requires=open('requirements.txt').read().splitlines(),
    python_requires='>=3.8',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    include_package_data=True,
    zip_safe=False
)
