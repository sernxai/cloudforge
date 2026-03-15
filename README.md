# CloudForge — Infrastructure as Code in Python

[Português Brasileiro (pt-BR)](README-pt-br.md)

**CloudForge** is an Infrastructure as Code (IaC) tool written in Python, inspired by Terraform, which allows you to define, provision, and manage resources across multiple cloud providers using declarative YAML files.

## Features

- **Multi-cloud**: AWS, GCP, Azure, **Alibaba Cloud** with unified abstraction
- **Native Firebase**: Auth, Firestore, Realtime Database, and Hosting
- **Cloud Run**: Serverless container deployment on GCP
- **Multi-provider DNS**: Integrated GoDaddy and Cloudflare (CNAME, A, TXT, MX)
- **Alibaba Cloud Support**: ECS, VPC, VSwitch, SLB, ACK
- **Declarative**: Entire infrastructure defined in YAML
- **Managed State**: Local control (JSON) with diff, backup, and rollback
- **Plan/Apply/Destroy**: Secure workflow with preview before applying
- **Advanced Logging**: Structured logging with Rich
- **Retry Logic**: Automatic retry with exponential backoff for transient errors

## Supported Resources

| Type | Description | Providers |
|---|---|---|
| vm | Virtual Machines | AWS, GCP, Azure, **Alibaba** |
| vpc | Virtual Private Cloud / VNet | AWS, GCP, Azure, **Alibaba** |
| subnet | Subnets | AWS, GCP, Azure, **Alibaba** |
| security_group | Firewall / NSG | AWS, GCP, Azure, **Alibaba** |
| kubernetes | K8s Clusters (EKS/GKE/AKS/ACK) | AWS, GCP, Azure, **Alibaba** |
| database | Managed Databases (RDS/SQL/etc) | AWS, GCP, Azure, **Alibaba** |
| cloud_run | Serverless Container | GCP |
| slb | Server Load Balancer | **Alibaba** |
| firebase_auth | Firebase Authentication | GCP |
| firestore | Cloud Firestore (NoSQL) | GCP |
| firebase_rtdb | Firebase Realtime Database | GCP |
| firebase_hosting | Static Hosting / SPA | GCP |
| dns_record | DNS Records (CNAME, A, TXT, MX) | GoDaddy, Cloudflare |

## CloudForge vs OpenTofu

While OpenTofu uses HCL (HashiCorp Configuration Language), CloudForge uses simple, declarative YAML. This makes it easier to read and integrate with other CI/CD tools.

### Example: Creating a VM/Instance

**OpenTofu (HCL):**
```hcl
resource "aws_instance" "example" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
}
```

**CloudForge (YAML):**
```yaml
- type: vm
  name: example-instance
  config:
    instance_type: small
    os: ubuntu-22.04
```

### Example: DNS Record

**OpenTofu (HCL):**
```hcl
resource "cloudflare_record" "www" {
  zone_id = "your-zone-id"
  name    = "www"
  value   = "192.0.2.1"
  type    = "A"
  ttl     = 3600
}
```

**CloudForge (YAML):**
```yaml
- type: dns_record
  name: www-record
  config:
    domain: example.com
    type: A
    name: www
    value: 192.0.2.1
    ttl: 3600
```

## Installation

```bash
pip install -r requirements.txt
# Or install as a package
pip install -e .
```

## Quick Start

```bash
cloudforge init --provider gcp --region southamerica-east1
cloudforge validate
cloudforge plan
cloudforge apply
cloudforge status
cloudforge output api-backend
cloudforge destroy
```

## Guide: GCP + Firebase + DNS (GoDaddy/Cloudflare)

### Prerequisites

```bash
# 1. Authenticate with GCP
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable APIs
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    firebasedatabase.googleapis.com \
    firebasehosting.googleapis.com \
    identitytoolkit.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

# 3. Enable Firebase
# https://console.firebase.google.com → Add project → select GCP project

# 4. Environment Variables
export GCP_PROJECT_ID="my-project-id"

# For GoDaddy:
export GODADDY_API_KEY="your_api_key"
export GODADDY_API_SECRET="your_api_secret"

# For Cloudflare:
export CLOUDFLARE_API_TOKEN="your_api_token"
```

### Complete Deployment

```bash
cloudforge plan          # Preview
cloudforge apply         # Provision everything

# Build and push the image
docker build -t gcr.io/$GCP_PROJECT_ID/api:latest .
docker push gcr.io/$GCP_PROJECT_ID/api:latest

# Deploy frontend
cd frontend && npm run build
firebase deploy --only hosting

# Check DNS
# (on Linux/macOS)
dig app.mydomain.com.br CNAME +short
# (on Windows PowerShell)
Resolve-DnsName app.mydomain.com.br -Type CNAME
```

## License

Apache 2.0

## Guide: Alibaba Cloud (Aliyun)

### Prerequisites

```bash
# 1. Install Alibaba Cloud SDK
pip install alibabacloud_ecs20140526 alibabacloud_vpc20160428 alibabacloud_slb20140515

# 2. Get your AccessKey
# Visit: https://ram.console.aliyun.com/manage/ak
# Create AccessKey for your user

# 3. Environment Variables
export ALIBABA_ACCESS_KEY_ID="your_access_key_id"
export ALIBABA_ACCESS_KEY_SECRET="your_access_key_secret"
export ALIBABA_REGION="cn-hangzhou"  # or cn-shanghai, cn-beijing, etc.
```

### Available Regions

| Region | Code |
|--------|------|
| China (Hangzhou) | `cn-hangzhou` |
| China (Shanghai) | `cn-shanghai` |
| China (Beijing) | `cn-beijing` |
| China (Shenzhen) | `cn-shenzhen` |
| Hong Kong | `cn-hongkong` |
| Singapore | `ap-southeast-1` |
| US (Silicon Valley) | `us-west-1` |
| Germany (Frankfurt) | `eu-central-1` |

### Example: Deploy VM on Alibaba Cloud

```yaml
project:
  name: alibaba-demo
  environment: development

provider:
  name: alibaba
  region: cn-hangzhou
  credentials:
    access_key: ${ALIBABA_ACCESS_KEY_ID}
    access_key_secret: ${ALIBABA_ACCESS_KEY_SECRET}

resources:
  # VPC
  - type: vpc
    name: main-vpc
    config:
      cidr_block: 10.0.0.0/16

  # VSwitch (Subnet)
  - type: subnet
    name: public-vswitch
    depends_on: [main-vpc]
    config:
      vpc: main-vpc
      cidr_block: 10.0.1.0/24
      availability_zone: cn-hangzhou-a

  # Security Group
  - type: security_group
    name: web-sg
    depends_on: [main-vpc]
    config:
      vpc: main-vpc
      ingress:
        - protocol: tcp
          port: 80
          cidr: 0.0.0.0/0
        - protocol: tcp
          port: 443
          cidr: 0.0.0.0/0
        - protocol: tcp
          port: 22
          cidr: 0.0.0.0/0

  # ECS Instance (VM)
  - type: vm
    name: web-server
    depends_on: [public-vswitch, web-sg]
    config:
      instance_type: medium
      os: ubuntu_22_04
      subnet: public-vswitch
      security_group: web-sg
      associate_public_ip: true

  # Server Load Balancer
  - type: slb
    name: web-lsb
    depends_on: [main-vpc, public-vswitch]
    config:
      public: true
      vpc: main-vpc
      subnet: public-vswitch
      bandwidth: 10
      listeners:
        - frontend_port: 80
          backend_port: 8080
```

### Deploy Commands

```bash
# Initialize project
cloudforge init --provider alibaba --region cn-hangzhou

# Validate configuration
cloudforge validate

# Preview changes
cloudforge plan

# Apply infrastructure
cloudforge apply

# Check status
cloudforge status

# Get VM outputs
cloudforge output web-server

# Destroy everything
cloudforge destroy
```
