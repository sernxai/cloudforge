## ☁️ CloudForge — Infrastructure as Code em Python

**CloudForge** é uma ferramenta de Infrastructure as Code (IaC) escrita em Python, inspirada no Terraform, que permite definir, provisionar e gerenciar recursos em múltiplos provedores de nuvem (AWS, GCP, Azure) usando arquivos YAML declarativos.

## Funcionalidades

- **Multi-cloud**: Suporte a AWS, GCP e Azure com abstração unificada
- **Declarativo**: Defina sua infraestrutura em YAML simples
- **Estado gerenciado**: Controle de estado local (JSON) para rastrear recursos
- **Plan/Apply/Destroy**: Fluxo seguro com preview antes de aplicar mudanças
- **Recursos suportados**:
  - VMs / Instâncias (EC2, Compute Engine, Azure VM)
  - Redes (VPC, Subnets, Security Groups / Firewalls)
  - Kubernetes (EKS, GKE, AKS)
  - Bancos de dados gerenciados (RDS, Cloud SQL, Azure Database)
- **Deploy Docker**: Pipeline integrado para build, push e deploy de containers

## Instalação

```bash
pip install -r requirements.txt
```

## Uso Rápido

```bash
# Inicializar projeto
cloudforge init --provider aws

# Validar configuração
cloudforge validate

# Planejar mudanças (dry-run)
cloudforge plan

# Aplicar infraestrutura
cloudforge apply

# Destruir infraestrutura
cloudforge destroy

# Deploy de container Docker
cloudforge deploy --image myapp:latest --target kubernetes
```

## Estrutura do Projeto

```
cloudforge/
├── cli.py                  # CLI principal (entry point)
├── core/
│   ├── engine.py           # Motor de orquestração
│   ├── state.py            # Gerenciamento de estado
│   ├── planner.py          # Geração de planos de execução
│   ├── graph.py            # Grafo de dependências entre recursos
│   └── config.py           # Parser de configuração YAML
├── providers/
│   ├── base.py             # Classe abstrata de provider
│   ├── aws/provider.py     # Provider AWS (boto3)
│   ├── gcp/provider.py     # Provider GCP (google-cloud)
│   └── azure/provider.py   # Provider Azure (azure-mgmt)
├── resources/
│   ├── base.py             # Classe abstrata de recurso
│   ├── vm.py               # Virtual Machines
│   ├── network.py          # VPC, Subnet, SecurityGroup
│   ├── kubernetes.py       # Clusters K8s
│   └── database.py         # Bancos de dados gerenciados
├── deploy/
│   └── docker_deployer.py  # Pipeline de deploy Docker
├── templates/              # Templates YAML de exemplo
│   └── infrastructure.yaml
├── requirements.txt
└── README.md
```

## Configuração de Exemplo

```yaml
project:
  name: minha-aplicacao
  environment: production

provider:
  name: aws
  region: us-east-1
  credentials:
    profile: default

resources:
  - type: vpc
    name: main-vpc
    config:
      cidr_block: "10.0.0.0/16"

  - type: subnet
    name: public-subnet
    depends_on: [main-vpc]
    config:
      vpc: main-vpc
      cidr_block: "10.0.1.0/24"
      availability_zone: us-east-1a
      public: true

  - type: kubernetes
    name: app-cluster
    depends_on: [public-subnet]
    config:
      node_count: 3
      node_type: t3.medium
      kubernetes_version: "1.28"

  - type: database
    name: app-db
    depends_on: [main-vpc]
    config:
      engine: postgresql
      version: "15"
      instance_type: db.t3.medium
      storage_gb: 100
      multi_az: true

deploy:
  type: docker
  image: myapp:latest
  target: app-cluster
  replicas: 3
  port: 8080
```

## Licença

Apache 2.0
