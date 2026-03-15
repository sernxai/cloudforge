# CloudForge - Novos Providers Adicionados

## Data: 2026-03-15

---

## 📋 Resumo

Foram adicionados **5 novos providers** ao CloudForge, totalizando **11 providers** suportados.

---

## ☁️ Novos Providers

### 1. Oracle Cloud Infrastructure (OCI) 🇺🇸

**Provider:** `oracle`

**Regiões:** 39 regiões globais
- Americas: US, Canada, Brazil (São Paulo, Vinhedo)
- Europe: UK, Germany, France, Netherlands, Spain, Italy, Switzerland
- Asia Pacific: Australia, Japan, Korea, India, Singapore
- Middle East & Africa: UAE, Saudi Arabia, South Africa

**Recursos Suportados:**
| Recurso | Descrição |
|---------|-----------|
| vm | Compute Instances (VMs) |
| vpc | VCN (Virtual Cloud Network) |
| subnet | Subnets |
| security_group | Security Lists |
| kubernetes | OKE (Oracle Kubernetes Engine) |
| database | Autonomous Database |
| lb | Load Balancer |

**Dependências:**
```bash
pip install oci>=2.100.0
```

**Exemplo de Configuração:**
```yaml
provider:
  name: oracle
  region: sa-saopaulo-1
  credentials:
    tenancy: ocid1.tenancy.oc1..xxx
    user: ocid1.user.oc1..xxx
    fingerprint: "xx:xx:xx:..."
    key_file: ~/.oci/oci_api_key.pem
```

---

### 2. DigitalOcean 🇺🇸

**Provider:** `digitalocean`

**Regiões:** 11 regiões
- US: NYC1, NYC2, NYC3, SFO1, SFO2, SFO3
- Europe: AMS2, AMS3, LON1, FRA1
- Asia: SGP1, BLR1
- Canada: TOR1
- Australia: SYD1

**Recursos Suportados:**
| Recurso | Descrição |
|---------|-----------|
| vm | Droplets (VMs) |
| vpc | VPC |
| subnet | VPC Subnets |
| security_group | Firewalls |
| kubernetes | DOKS (DigitalOcean Kubernetes) |
| database | Managed Databases (PostgreSQL, MySQL, Redis, MongoDB) |
| lb | Load Balancers |

**Dependências:**
```bash
# requests já incluído no core
```

**Exemplo de Configuração:**
```yaml
provider:
  name: digitalocean
  region: nyc3
  credentials:
    api_token: ${DO_API_TOKEN}
```

---

### 3. Hetzner Cloud 🇩🇪

**Provider:** `hetzner`

**Regiões:** 3 regiões
- eu-central: Falkenstein, Germany
- eu-west: Nuremberg, Germany
- us-east: Ashburn, VA, USA

**Recursos Suportados:**
| Recurso | Descrição |
|---------|-----------|
| vm | Cloud Servers (VMs) |
| vpc | Networks |
| subnet | Network Subnets |
| security_group | Firewalls |
| lb | Load Balancers |

**Dependências:**
```bash
# requests já incluído no core
```

**Exemplo de Configuração:**
```yaml
provider:
  name: hetzner
  region: eu-central
  credentials:
    api_token: ${HETZNER_API_TOKEN}
```

---

### 4. Hostinger 🇱🇹

**Provider:** `hostinger`

**Regiões:** 8 regiões
- US, UK, France, India, Indonesia, Brazil, Lithuania, Singapore

**Recursos Suportados:**
| Recurso | Descrição |
|---------|-----------|
| vm | VPS (Virtual Private Servers) |
| website | Web Hosting |
| database | MySQL Databases |
| dns_record | DNS Records |

**Dependências:**
```bash
# requests já incluído no core
```

**Exemplo de Configuração:**
```yaml
provider:
  name: hostinger
  region: br
  credentials:
    api_key: ${HOSTINGER_API_KEY}
```

---

### 5. Locaweb 🇧🇷

**Provider:** `locaweb`

**Regiões:** 2 regiões (Brasil)
- br-sudeste: São Paulo
- br-nordeste: Recife

**Recursos Suportados:**
| Recurso | Descrição |
|---------|-----------|
| vm | Simple Server (VMs) |
| vpc | Redes Virtuais |
| subnet | Subnets |
| security_group | Grupos de Segurança |
| lb | Load Balancers |
| website | Hospedagem de Sites |
| database | Bancos de Dados (MySQL, PostgreSQL, SQL Server) |

**Dependências:**
```bash
# requests já incluído no core
```

**Exemplo de Configuração:**
```yaml
provider:
  name: locaweb
  region: br-sudeste
  credentials:
    api_key: ${LOCOWEB_API_KEY}
    account_id: ${LOCOWEB_ACCOUNT_ID}
```

---

## 📊 Comparação de Providers

| Provider | Regiões | Recursos | Preço (VM básica) |
|----------|---------|----------|-------------------|
| Oracle | 39 | 7 | $0.0061/hora |
| DigitalOcean | 11 | 7 | $4/mês |
| Hetzner | 3 | 5 | €4.51/mês |
| Hostinger | 8 | 4 | €3.99/mês |
| Locaweb | 2 | 7 | R$ 35/mês |

---

## 🚀 Comandos CLI Atualizados

### Listar todos os providers
```bash
cloudforge providers
```

### Inicializar projeto com novo provider
```bash
# Oracle Cloud
cloudforge init --provider oracle --region sa-saopaulo-1

# DigitalOcean
cloudforge init --provider digitalocean --region nyc3

# Hetzner
cloudforge init --provider hetzner --region eu-central

# Hostinger
cloudforge init --provider hostinger --region br

# Locaweb
cloudforge init --provider locaweb --region br-sudeste
```

### Instalar dependências
```bash
# Oracle
cloudforge install-deps oracle

# DigitalOcean
cloudforge install-deps digitalocean

# Hetzner
cloudforge install-deps hetzner

# Hostinger
cloudforge install-deps hostinger

# Locaweb
cloudforge install-deps locaweb
```

---

## 📦 Instalação Modular

### Via pip
```bash
# Oracle Cloud
pip install cloudforge[oracle]

# DigitalOcean
pip install cloudforge[digitalocean]

# Hetzner
pip install cloudforge[hetzner]

# Hostinger
pip install cloudforge[hostinger]

# Locaweb
pip install cloudforge[locaweb]

# Todos os providers
pip install cloudforge[all]
```

### Via requirements files
```bash
# Oracle
pip install -r requirements-oracle.txt

# DigitalOcean
pip install -r requirements-digitalocean.txt

# Hetzner
pip install -r requirements-hetzner.txt

# Hostinger
pip install -r requirements-hostinger.txt

# Locaweb
pip install -r requirements-locaweb.txt
```

---

## 🔧 Arquivos Criados/Modificados

### Criados (15)
- `cloudforge/providers/oracle/provider.py`
- `cloudforge/providers/oracle/__init__.py`
- `cloudforge/providers/digitalocean/provider.py`
- `cloudforge/providers/digitalocean/__init__.py`
- `cloudforge/providers/hetzner/provider.py`
- `cloudforge/providers/hetzner/__init__.py`
- `cloudforge/providers/hostinger/provider.py`
- `cloudforge/providers/hostinger/__init__.py`
- `cloudforge/providers/locaweb/provider.py`
- `cloudforge/providers/locaweb/__init__.py`
- `requirements-oracle.txt`
- `requirements-digitalocean.txt`
- `requirements-hetzner.txt`
- `requirements-hostinger.txt`
- `requirements-locaweb.txt`

### Modificados (4)
- `cloudforge/core/engine.py` - PROVIDER_REGISTRY e get_provider()
- `cloudforge/cli.py` - Comando init atualizado
- `setup.py` - extras_require atualizado
- `requirements.txt` - includes modulares

---

## ✅ Total de Providers Suportados

| # | Provider | Tipo | Recursos |
|---|----------|------|----------|
| 1 | AWS | hyperscaler | 6 |
| 2 | GCP | hyperscaler | 11 |
| 3 | Azure | hyperscaler | 6 |
| 4 | Alibaba | hyperscaler | 7 |
| 5 | Oracle | hyperscaler | 7 |
| 6 | DigitalOcean | cloud | 7 |
| 7 | Hetzner | cloud | 5 |
| 8 | Hostinger | hosting | 4 |
| 9 | Locaweb | hosting/cloud | 7 |
| 10 | GoDaddy | dns | 1 |
| 11 | Cloudflare | dns | 1 |

**Total: 11 providers** com **~60 recursos** diferentes

---

## 🎯 Casos de Uso

### Oracle Cloud
- Empresas já usando Oracle Database
- Aplicações enterprise que precisam de alta performance
- Multi-cloud com foco em América Latina (região em São Paulo)

### DigitalOcean
- Startups e desenvolvedores
- Aplicações web simples
- Kubernetes gerenciado acessível

### Hetzner
- Projetos europeus (GDPR compliance)
- Custo-benefício para VMs
- Baixa latência na Europa

### Hostinger
- Hospedagem de sites
- Pequenos negócios
- VPS econômico

### Locaweb
- Empresas brasileiras
- Compliance com LGPD
- Suporte em português
- Baixa latência no Brasil

---

## 📝 Próximos Passos

1. **Adicionar mais recursos** por provider
2. **Implementar testes** específicos para cada provider
3. **Documentação detalhada** de cada recurso
4. **Exemplos de configuração** para casos de uso comuns
5. **Suporte a multi-provider** em um único projeto

---

**CloudForge Team** - 2026-03-15
Licença: Apache 2.0
