from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="cloudforge",
    version="1.0.0",
    description="Infrastructure as Code em Python — multi-cloud (AWS, GCP, Azure)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="CloudForge Team",
    python_requires=">=3.11",
    packages=find_packages(),
    include_package_data=True,
    package_data={"": ["templates/*.yaml"]},
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "cloudforge=cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
