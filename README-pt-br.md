# CloudForge — Infrastructure as Code em Python

[English (EN)](README.md)

**CloudForge** é uma ferramenta de Infrastructure as Code (IaC) escrita em Python, inspirada no Terraform, que permite definir, provisionar e gerenciar recursos em múltiplos provedores de nuvem usando arquivos YAML declarativos.

## Funcionalidades

- **Multi-cloud**: AWS, GCP, Azure, **Alibaba Cloud** com abstração unificada
- **Firebase nativo**: Auth, Firestore, Realtime Database e Hosting
- **Cloud Run**: Deploy serverless de containers no GCP
- **DNS multi-provider**: GoDaddy e Cloudflare (CNAME, A, TXT, MX) integrado
- **Suporte Alibaba Cloud**: ECS, VPC, VSwitch, SLB, ACK
- **Declarativo**: Infraestrutura inteira definida em YAML
- **Estado gerenciado**: Controle local (JSON) com diff, backup e rollback
- **Plan/Apply/Destroy**: Fluxo seguro com preview antes de aplicar
- **Logging avançado**: Logging estruturado com Rich
- **Retry automático**: Backoff exponencial para erros transitórios

## Recursos Suportados

| Tipo | Descrição | Providers |
|---|---|---|
| vm | Máquinas virtuais | AWS, GCP, Azure, **Alibaba** |
| vpc | Virtual Private Cloud / VNet | AWS, GCP, Azure, **Alibaba** |
| subnet | Sub-redes | AWS, GCP, Azure, **Alibaba** |
| security_group | Firewall / NSG | AWS, GCP, Azure, **Alibaba** |
| kubernetes | Clusters K8s (EKS/GKE/AKS/ACK) | AWS, GCP, Azure, **Alibaba** |
| database | Bancos gerenciados (RDS/SQL/etc) | AWS, GCP, Azure, **Alibaba** |
| cloud_run | Container serverless | GCP |
| slb | Load Balancer | **Alibaba** |
| firebase_auth | Autenticação Firebase | GCP |
| firestore | Cloud Firestore (NoSQL) | GCP |
| firebase_rtdb | Firebase Realtime Database | GCP |
| firebase_hosting | Hosting estático / SPA | GCP |
| dns_record | Registros DNS (CNAME, A, TXT, MX) | GoDaddy, Cloudflare |

## CloudForge vs OpenTofu

Enquanto o OpenTofu utiliza HCL (HashiCorp Configuration Language), o CloudForge utiliza YAML simples e declarativo. Isso torna a leitura mais fácil e a integração com outras ferramentas de CI/CD mais natural.

### Exemplo: Criando uma VM/Instância

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

### Exemplo: Registro de DNS

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
    domain: exemplo.com
    type: A
    name: www
    value: 192.0.2.1
    ttl: 3600
```

## Instalação

```bash
pip install -r requirements.txt
```

## Uso Rápido

```bash
cloudforge init --provider gcp --region southamerica-east1
cloudforge validate
cloudforge plan
cloudforge apply
cloudforge status
cloudforge output api-backend
cloudforge destroy
```

## Guia: GCP + Firebase + DNS (GoDaddy/Cloudflare)

### Pré-requisitos

```bash
# 1. Autenticar no GCP
gcloud auth application-default login
gcloud config set project SEU_PROJECT_ID

# 2. Habilitar APIs
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    firebasedatabase.googleapis.com \
    firebasehosting.googleapis.com \
    identitytoolkit.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

# 3. Habilitar Firebase
# https://console.firebase.google.com → Adicionar projeto → selecionar GCP project

# 4. Variáveis de ambiente
export GCP_PROJECT_ID="meu-projeto-id"

# Para GoDaddy:
export GODADDY_API_KEY="sua_api_key"
export GODADDY_API_SECRET="seu_api_secret"

# Para Cloudflare:
export CLOUDFLARE_API_TOKEN="seu_api_token"
```

### Deploy Completo

```bash
cloudforge plan          # Preview
cloudforge apply         # Provisionar tudo

# Build e push da imagem
docker build -t gcr.io/$GCP_PROJECT_ID/api:latest .
docker push gcr.io/$GCP_PROJECT_ID/api:latest

# Deploy frontend
cd frontend && npm run build
firebase deploy --only hosting

# Verificar DNS
dig app.meudominio.com.br CNAME +short
```

## Guia: Alibaba Cloud (Aliyun)

### Pré-requisitos

```bash
# 1. Instalar SDK da Alibaba Cloud
pip install alibabacloud_ecs20140526 alibabacloud_vpc20160428 alibabacloud_slb20140515

# 2. Obter AccessKey
# Acesse: https://ram.console.aliyun.com/manage/ak
# Crie um AccessKey para seu usuário

# 3. Variáveis de Ambiente
export ALIBABA_ACCESS_KEY_ID="seu_access_key_id"
export ALIBABA_ACCESS_KEY_SECRET="seu_access_key_secret"
export ALIBABA_REGION="cn-hangzhou"  # ou cn-shanghai, cn-beijing, etc.
```

### Regiões Disponíveis

| Região | Código |
|--------|------|
| China (Hangzhou) | `cn-hangzhou` |
| China (Shanghai) | `cn-shanghai` |
| China (Beijing) | `cn-beijing` |
| China (Shenzhen) | `cn-shenzhen` |
| Hong Kong | `cn-hongkong` |
| Singapura | `ap-southeast-1` |
| EUA (Silicon Valley) | `us-west-1` |
| Alemanha (Frankfurt) | `eu-central-1` |

### Exemplo: Deploy de VM na Alibaba Cloud

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

  # Instância ECS (VM)
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

### Comandos de Deploy

```bash
# Inicializar projeto
cloudforge init --provider alibaba --region cn-hangzhou

# Validar configuração
cloudforge validate

# Preview das mudanças
cloudforge plan

# Aplicar infraestrutura
cloudforge apply

# Verificar status
cloudforge status

# Obter outputs da VM
cloudforge output web-server

# Destruir tudo
cloudforge destroy
```

## Licença

Apache 2.0
