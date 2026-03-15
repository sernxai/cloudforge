# CloudForge — Infrastructure as Code in Python

[Português Brasileiro (pt-BR)](README-pt-br.md)

**CloudForge** is an Infrastructure as Code (IaC) tool written in Python, inspired by Terraform, which allows you to define, provision, and manage resources across multiple cloud providers using declarative YAML files.

## Features

- **Multi-cloud**: AWS, GCP, and Azure with unified abstraction
- **Native Firebase**: Auth, Firestore, Realtime Database, and Hosting
- **Cloud Run**: Serverless container deployment on GCP
- **Multi-provider DNS**: Integrated GoDaddy (CNAME, A, TXT, MX)
- **Declarative**: Entire infrastructure defined in YAML
- **Managed State**: Local control (JSON) with diff, backup, and rollback
- **Plan/Apply/Destroy**: Secure workflow with preview before applying

## Supported Resources

| Type | Description | Providers |
|---|---|---|
| vm | Virtual Machines | AWS, GCP, Azure |
| vpc | Virtual Private Cloud / VNet | AWS, GCP, Azure |
| subnet | Subnets | AWS, GCP, Azure |
| security_group | Firewall / NSG | AWS, GCP, Azure |
| kubernetes | K8s Clusters (EKS/GKE/AKS) | AWS, GCP, Azure |
| database | Managed Databases (RDS/SQL/etc) | AWS, GCP, Azure |
| cloud_run | Serverless Container | GCP |
| firebase_auth | Firebase Authentication | GCP |
| firestore | Cloud Firestore (NoSQL) | GCP |
| firebase_rtdb | Firebase Realtime Database | GCP |
| firebase_hosting | Static Hosting / SPA | GCP |
| dns_record | DNS Records (CNAME, A, TXT, MX) | GoDaddy |

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

## Guide: GCP + Firebase + GoDaddy

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
export GODADDY_API_KEY="your_api_key"
export GODADDY_API_SECRET="your_api_secret"
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

MIT
