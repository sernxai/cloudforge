# CloudForge - Guia de Instalação Modular

## Visão Geral

O CloudForge agora suporta instalação modular de dependências. Isso significa que você pode instalar apenas as dependências dos providers que vai utilizar, reduzindo o tamanho da instalação e o tempo de setup.

## Instalação Básica (Core)

A instalação básica inclui apenas as dependências essenciais do CloudForge:

```bash
pip install cloudforge
```

**Inclui:**
- CLI e engine principal
- Gerenciamento de estado
- Validação de schema
- Logging e retry
- Suporte a YAML e JSON

**Não inclui:** Nenhum provider de nuvem

## Instalação por Provider

### AWS

```bash
pip install cloudforge[aws]
```

**Recursos disponíveis:**
- VM (EC2)
- VPC
- Subnet
- Security Group
- Kubernetes (EKS)
- Database (RDS)

**Dependências instaladas:**
- boto3>=1.34.0

---

### Google Cloud Platform

```bash
pip install cloudforge[gcp]
```

**Recursos disponíveis:**
- VM (Compute Engine)
- VPC
- Subnet
- Security Group
- Kubernetes (GKE)
- Database (Cloud SQL)
- Cloud Run
- Firebase Auth
- Firestore
- Firebase Realtime Database
- Firebase Hosting

**Dependências instaladas:**
- google-cloud-compute>=1.16.0
- google-cloud-container>=2.38.0
- google-cloud-run>=0.10.0
- google-cloud-firestore>=2.16.0
- cloud-sql-python-connector>=1.12.0
- firebase-admin>=6.5.0
- google-auth>=2.28.0

---

### Microsoft Azure

```bash
pip install cloudforge[azure]
```

**Recursos disponíveis:**
- VM
- VPC (VNet)
- Subnet
- Security Group (NSG)
- Kubernetes (AKS)
- Database (SQL Database)

**Dependências instaladas:**
- azure-mgmt-compute>=30.0.0
- azure-mgmt-network>=25.0.0
- azure-mgmt-containerservice>=28.0.0
- azure-mgmt-rdbms>=10.1.0
- azure-identity>=1.15.0

---

### Alibaba Cloud

```bash
pip install cloudforge[alibaba]
```

**Recursos disponíveis:**
- VM (ECS)
- VPC
- Subnet (VSwitch)
- Security Group
- SLB (Load Balancer)
- Kubernetes (ACK)
- Database (RDS)

**Dependências instaladas:**
- alibabacloud_ecs20140526>=3.0.0
- alibabacloud_vpc20160428>=2.0.0
- alibabacloud_slb20140515>=2.0.0
- alibabacloud_tea_openapi>=0.3.0
- alibabacloud_credentials>=0.3.0

---

### DNS Providers

```bash
pip install cloudforge[dns]
```

**Recursos disponíveis:**
- DNS Record (GoDaddy, Cloudflare)

**Dependências instaladas:**
- Nenhuma adicional (usa requests do core)

---

## Instalação Completa

Para instalar todos os providers de uma vez:

```bash
pip install cloudforge[all]
```

Ou usando o requirements.txt completo:

```bash
pip install -r requirements.txt
```

---

## Instalação Múltipla

Você pode instalar múltiplos providers combinando os extras:

```bash
pip install cloudforge[aws,gcp]
```

Ou instalar separadamente:

```bash
pip install cloudforge[aws]
pip install cloudforge[alibaba]
```

---

## Usando requirements Modulares

O projeto inclui arquivos requirements separados para cada provider:

| Arquivo | Descrição |
|---------|-----------|
| `requirements-core.txt` | Dependências básicas (obrigatório) |
| `requirements-aws.txt` | Provider AWS |
| `requirements-gcp.txt` | Provider GCP |
| `requirements-azure.txt` | Provider Azure |
| `requirements-alibaba.txt` | Provider Alibaba Cloud |
| `requirements-godaddy.txt` | Provider GoDaddy DNS |
| `requirements-cloudflare.txt` | Provider Cloudflare DNS |
| `requirements.txt` | Todos os providers |

### Exemplo de uso:

```bash
# Apenas GCP
pip install -r requirements-core.txt
pip install -r requirements-gcp.txt

# AWS + Alibaba
pip install -r requirements-core.txt
pip install -r requirements-aws.txt
pip install -r requirements-alibaba.txt
```

---

## Comandos CLI Úteis

### Listar providers disponíveis

```bash
cloudforge providers
```

Exibe todos os providers suportados, regiões disponíveis e recursos.

### Instalar dependências de um provider

```bash
cloudforge install-deps aws
cloudforge install-deps gcp
cloudforge install-deps alibaba
```

### Listar opções de instalação

```bash
cloudforge install-deps
```

---

## Verificando Instalação

Após instalar um provider, você pode verificar se está funcionando:

```bash
cloudforge providers
```

O provider instalado aparecerá sem avisos de dependências faltando.

---

## Exemplo de Projeto

### Cenário: Projeto usando apenas GCP

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows

# 2. Instalar CloudForge + GCP
pip install cloudforge[gcp]

# 3. Inicializar projeto
cloudforge init --provider gcp --region southamerica-east1

# 4. Validar e aplicar
cloudforge validate
cloudforge plan
cloudforge apply
```

### Cenário: Projeto multi-cloud (AWS + Alibaba)

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# 2. Instalar CloudForge + AWS + Alibaba
pip install cloudforge[aws,alibaba]

# 3. Inicializar projeto com AWS
cloudforge init --provider aws --region us-east-1

# 4. Editar infrastructure.yaml para usar ambos providers
# (via external_cloudforge)

# 5. Validar e aplicar
cloudforge validate
cloudforge plan
cloudforge apply
```

---

## Economia de Espaço

Comparação de tamanho de instalação:

| Instalação | Espaço Aproximado |
|------------|-------------------|
| Core apenas | ~50 MB |
| + AWS | ~80 MB |
| + GCP | ~150 MB |
| + Azure | ~200 MB |
| + Alibaba | ~120 MB |
| Todos (all) | ~500 MB |

**Nota:** Valores aproximados, podem variar.

---

## Troubleshooting

### Erro: "Provider não encontrado"

Verifique se o provider está instalado:

```bash
pip show cloudforge
pip list | grep -E "boto3|google-cloud|azure|alibabacloud"
```

### Erro: "Módulo não encontrado"

Reinstale as dependências do provider:

```bash
cloudforge install-deps aws --upgrade
```

Ou:

```bash
pip install --upgrade cloudforge[aws]
```

### Conflito de Dependências

Se houver conflito entre versões de pacotes, use um ambiente virtual separado para cada projeto:

```bash
python -m venv project1-venv
python -m venv project2-venv
```

---

## Dicas

1. **Use ambientes virtuais**: Sempre use um venv por projeto para isolar dependências.

2. **Instale apenas o necessário**: Se seu projeto usa apenas GCP, não instale AWS/Azure.

3. **Congele dependências**: Em produção, use `pip freeze > requirements.txt` para travar versões.

4. **Verifique compatibilidade**: Alguns providers podem ter dependências conflitantes.

---

## Suporte

Para mais informações:
- Documentação: `README.md`
- Exemplos: `infrastructure-alibaba-example.yaml`
- Issues: GitHub repository

---

**CloudForge** - Infrastructure as Code em Python
Licença: Apache 2.0
