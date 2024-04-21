# Import required functions
from setuptools import setup, find_packages

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Call setup function
setup(
    author="Javad Ebadi",
    author_email="javad@javadebadi.com",
    description="A simple python wrapper for crypto.com API",
    name="python-crypto-dot-com-sdk",
    packages=find_packages(include=["crypto_dot_com", "crypto_dot_com.*"]),
    version="0.0.0",
    install_requires=['requests'],
    python_requires='>=3.7',
    license='MIT',
    url='https://github.com/javadebadi/python-crypto-dot-com-sdk',
    long_description=long_description,
    long_description_content_type='text/markdown'
)
