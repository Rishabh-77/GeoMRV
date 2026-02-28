from setuptools import find_packages, setup

setup(
    name="geomrv",
    version="0.1.0",
    description="GeoMRV carbon monitoring platform",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.11",
)
