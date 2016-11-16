from distutils.core import setup

classifiers = [
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Topic :: Database',
]

setup(
    name="nmongo",
    version=__import__('nmongo').__version__,
    url='https://github.com/nakagami/nmongo/',
    classifiers=classifiers,
    keywords=['MongoDB'],
    author='Hajime Nakagami',
    author_email='nakagami@gmail.com',
    description='Yet another MongoDB driver',
    long_description=open('README.rst').read(),
    license="MIT",
    py_modules=['nmongo'],
)
