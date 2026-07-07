from setuptools import setup, find_packages

setup(
    name="celltrackscolab",
    version="1.0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=PYTHON_VERSION",
    install_requires=[
    ],
)
