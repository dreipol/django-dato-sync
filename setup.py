import os

from setuptools import setup

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

reqs = ['Django>=5.0']

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-dato-sync',
    version='1.0.0',
    packages=['dato_sync'],
    include_package_data=True,
    license='MIT License',
    description='django-dato-sync lets you import data from DatoCMS into the django DB',
    long_description=README,
    url='https://www.dreipol.ch/',
    author='dreipol AG',
    author_email='dev@dreipol.ch',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=reqs,
)
