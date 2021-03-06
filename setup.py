import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = ['repoze.bfg', 'supervisor', 'amqplib', 'eventlet', 'repoze.bfg.jinja2', 'psutil', 'psi']

setup(name='multivisor',
      version='0.0',
      description='multivisor',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: BFG",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg',
      packages=find_packages(),
      py_modules=['baker'],
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="multivisor",
      entry_points = {
      'paste.app_factory': ['app = multivisor.run:app'],
      'paste.server_factory': ['eventlet_server = multivisor.server.factory:server_factory'],
      'console_scripts': [
              'listener = multivisor.listener:run',
              'amqp = multivisor.amqp.commands:main',
              ]
      }
      )

