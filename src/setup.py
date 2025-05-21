from setuptools import setup, find_packages

setup(name='watts',
      version='0.1',
      description='',
      packages=find_packages(),
      package_data={'': ['*.json', '*.txt', '*.omn', '*.xml']},
      include_package_data=True
      )
