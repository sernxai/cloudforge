from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Dependências core (obrigatórias)
with open("requirements-core.txt", "r", encoding="utf-8") as f:
    core_requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

# Dependências por provider (opcionais)
aws_requirements = [
    "boto3>=1.34.0",
]

gcp_requirements = [
    "google-cloud-compute>=1.16.0",
    "google-cloud-container>=2.38.0",
    "google-cloud-run>=0.10.0",
    "google-cloud-firestore>=2.16.0",
    "cloud-sql-python-connector>=1.12.0",
    "firebase-admin>=6.5.0",
    "google-auth>=2.28.0",
]

azure_requirements = [
    "azure-mgmt-compute>=30.0.0",
    "azure-mgmt-network>=25.0.0",
    "azure-mgmt-containerservice>=28.0.0",
    "azure-mgmt-rdbms>=10.1.0",
    "azure-identity>=1.15.0",
]

alibaba_requirements = [
    "alibabacloud_ecs20140526>=3.0.0",
    "alibabacloud_vpc20160428>=2.0.0",
    "alibabacloud_slb20140515>=2.0.0",
    "alibabacloud_tea_openapi>=0.3.0",
    "alibabacloud_credentials>=0.3.0",
]

oracle_requirements = [
    "oci>=2.100.0",
]

digitalocean_requirements = [
    # requests já incluído no core
]

hetzner_requirements = [
    # requests já incluído no core
]

hostinger_requirements = [
    # requests já incluído no core
]

locaweb_requirements = [
    # requests já incluído no core
]

ovh_requirements = [
    "ovh>=1.0.0",
]

setup(
    name="cloudforge",
    version="1.0.0",
    description="Infrastructure as Code em Python — multi-cloud (AWS, GCP, Azure, Alibaba, Oracle, DigitalOcean, Hetzner, Hostinger, Locaweb, OVHCloud)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="CloudForge Team",
    python_requires=">=3.11",
    packages=find_packages(),
    include_package_data=True,
    package_data={"": ["templates/*.yaml"]},
    install_requires=core_requirements,
    extras_require={
        "aws": aws_requirements,
        "gcp": gcp_requirements,
        "azure": azure_requirements,
        "alibaba": alibaba_requirements,
        "oracle": oracle_requirements,
        "digitalocean": digitalocean_requirements,
        "hetzner": hetzner_requirements,
        "hostinger": hostinger_requirements,
        "locaweb": locaweb_requirements,
        "ovh": ovh_requirements,
        "dns": [],  # GoDaddy e Cloudflare usam requests (já incluído no core)
        "all": (
            aws_requirements +
            gcp_requirements +
            azure_requirements +
            alibaba_requirements +
            oracle_requirements +
            ovh_requirements
        ),
    },
    entry_points={
        "console_scripts": [
            "cloudforge=cloudforge.cli:cli",
        ],
    },
    license="Apache-2.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="iac infrastructure terraform cloud aws gcp azure alibaba oracle digitalocean hetzner hostinger locaweb ovh",
)
