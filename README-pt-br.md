# CloudForge — Infrastructure as Code em Python

[English (EN)](README.md)

**CloudForge** é uma ferramenta de Infrastructure as Code (IaC) escrita em Python, inspirada no Terraform, que permite definir, provisionar e gerenciar recursos em múltiplos provedores de nuvem usando arquivos YAML declarativos.

## Funcionalidades

- **Multi-cloud**: AWS, GCP e Azure com abstração unificada
- **Firebase nativo**: Auth, Firestore, Realtime Database e Hosting
- **Cloud Run**: Deploy serverless de containers no GCP
- **DNS multi-provider**: GoDaddy (CNAME, A, TXT, MX) integrado
- **Declarativo**: Infraestrutura inteira definida em YAML
- **Estado gerenciado**: Controle local (JSON) com diff, backup e rollback
- **Plan/Apply/Destroy**: Fluxo seguro com preview antes de aplicar

## Recursos Suportados

| Tipo | Descrição | Providers |
|---|---|---|
| vm | Máquinas virtuais | AWS, GCP, Azure |
| vpc | Virtual Private Cloud / VNet | AWS, GCP, Azure |
| subnet | Sub-redes | AWS, GCP, Azure |
| security_group | Firewall / NSG | AWS, GCP, Azure |
| kubernetes | Clusters K8s (EKS/GKE/AKS) | AWS, GCP, Azure |
| database | Bancos gerenciados (RDS/SQL/etc) | AWS, GCP, Azure |
| cloud_run | Container serverless | GCP |
| firebase_auth | Autenticação Firebase | GCP |
| firestore | Cloud Firestore (NoSQL) | GCP |
| firebase_rtdb | Firebase Realtime Database | GCP |
| firebase_hosting | Hosting estático / SPA | GCP |
| dns_record | Registros DNS (CNAME, A, TXT, MX) | GoDaddy |

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

## Guia: GCP + Firebase + GoDaddy

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
export GODADDY_API_KEY="sua_api_key"
export GODADDY_API_SECRET="seu_api_secret"
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

## Licença

MIT
