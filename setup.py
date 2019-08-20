import io
import re
from setuptools import setup


with io.open("README.rst", "rt", encoding="utf8") as f:
    readme = f.read()

with io.open("rarog/__init__.py", "rt", encoding="utf8") as f:
    version = re.search(r"__version__ = '(.*?)'", f.read()).group(1)

setup(
    name="rarog",
    version=version,
    url="https://github.com/ikhlestov/rarog",
    project_urls={
        "Code": "https://github.com/ikhlestov/rarog",
    },
    license="Apache 2",
    description="Monitoring utility for machine learning experiments",
    long_description=readme,
    author="Illarion Khlestov",
    author_email="khlyestovillarion@gmail.com",
    maintainer="Illarion Khlestov",
    maintainer_email="khlyestovillarion@gmail.com",
    packages=["rarog"],
    include_package_data=True,
    python_requires=">=3.4.0",
    install_requires=["clickhouse-driver", "numpy"]
)
