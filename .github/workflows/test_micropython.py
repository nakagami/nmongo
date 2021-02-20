# This workflow will install Python dependencies, run tests and lint with a variety of Python versions
# For more information see: https://help.github.com/actions/language-and-framework-guides/using-python-with-github-actions

name: MicroPython package

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

jobs:
  build:

    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Start MongoDB
      uses: supercharge/mongodb-github-action@1.3.0
      with:
        mongodb-version: 3.6
    - name: Install MicroPython
      run: |
        sudo apt install micropython
        micropython -m upip install micropython-errno
        micropython -m upip install micropython-os
        micropython -m upip install micropython-socket
        micropython -m upip install micropython-time
        micropython -m upip install micropython-datetime
        micropython -m upip install micropython-binascii
        micropython -m upip install micropython-random
        micropython -m upip install micropython-struct
        micropython -m upip install micropython-base64
        micropython -m upip install micropython-unittest
    - name: Test
      run: |
        micropython test_nmongo.py
