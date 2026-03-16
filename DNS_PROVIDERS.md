# CloudForge - DNS em Todos os Providers

## Resumo

Implementamos suporte a DNS em todos os principais providers de nuvem, permitindo gerenciar registros DNS de forma unificada através do CloudForge.

---

## Providers com Suporte a DNS

### 1. AWS - Route53 ✅

**Recursos:** `dns_record`

**Tipos de Registro Suportados:**
- A, AAAA, CNAME, MX, TXT, NS, PTR, SOA, SRV, CAA

**Exemplo de Uso:**
```yaml
provider:
  name: aws
  region: us-east-1

resources:
  - type: dns_record
    name: www-record
    config:
      hosted_zone: Z1234567890ABC  # ou domain: example.com
      name: www
      type: A
      value: 192.0.2.1
      ttl: 300
```

**Comando:**
```bash
cloudforge init --provider aws --region us-east-1
```

---

### 2. Google Cloud - Cloud DNS ✅

**Recursos:** `dns_record`

**Tipos de Registro Suportados:**
- A, AAAA, CNAME, MX, TXT, NS, PTR, SOA, SRV, CAA, NAPTR, SPF

**Exemplo de Uso:**
```yaml
provider:
  name: gcp
  region: us-central1

resources:
  - type: dns_record
    name: api-record
    config:
      zone: example-com-zone
      name: api
      type: CNAME
      value: www.example.com
      ttl: 3600
```

**Comando:**
```bash
cloudforge init --provider gcp --region us-central1
```

---

### 3. Azure - DNS Zones ✅

**Recursos:** `dns_record`

**Tipos de Registro Suportados:**
- A, AAAA, CNAME, MX, TXT, NS, PTR, SOA, SRV, CAA

**Exemplo de Uso:**
```yaml
provider:
  name: azure
  region: eastus

resources:
  - type: dns_record
    name: mail-record
    config:
      resource_group: dns-rg
      zone: example.com
      name: "@"
      type: MX
      value: mail.example.com
      priority: 10
      ttl: 3600
```

**Comando:**
```bash
cloudforge init --provider azure --region eastus
```

---

### 4. GoDaddy - DNS + Domínios + Hospedagem ✅

**Recursos:** `dns_record`, `domain`, `hosting`

**Tipos de Registro Suportados:**
- A, AAAA, CNAME, MX, TXT, NS, PTR, SRV, CAA

**Exemplo de Uso:**
```yaml
external_cloudforge:
  providers:
    godaddy:
      api_key: ${GODADDY_API_KEY}
      api_secret: ${GODADDY_API_SECRET}
      environment: production

resources:
  # DNS
  - type: dns_record
    name: www-godaddy
    config:
      domain: example.com
      record_type: CNAME
      record_name: www
      record_value: @
      ttl: 3600

  # Domínio
  - type: domain
    name: register-domain
    config:
      domain: mynewdomain.com
      years: 1
      privacy: true
      auto_renew: true

  # Hospedagem
  - type: hosting
    name: setup-hosting
    config:
      domain: mynewdomain.com
      plan: economy
      duration: 12
```

**Comando:**
```bash
cloudforge install-deps godaddy
```

---

### 5. Hostinger - DNS ✅

**Recursos:** `dns_record`

**Exemplo de Uso:**
```yaml
provider:
  name: hostinger
  region: br

resources:
  - type: dns_record
    name: blog-record
    config:
      domain: example.com.br
      name: blog
      type: A
      value: 192.0.2.1
      ttl: 3600
```

---

### 6. Cloudflare - DNS ✅

**Recursos:** `dns_record`

**Exemplo de Uso:**
```yaml
external_cloudforge:
  providers:
    cloudflare:
      api_token: ${CLOUDFLARE_API_TOKEN}

resources:
  - type: dns_record
    name: cdn-record
    config:
      domain: example.com
      name: cdn
      type: CNAME
      value: cdn.cloudflare.net
      ttl: 3600
```

---

## Comparação de Recursos DNS

| Provider | Tipos | Preço (por milhão queries) | TTL Mínimo |
|----------|-------|---------------------------|------------|
| AWS Route53 | 12+ | $0.40 | 1s |
| GCP Cloud DNS | 14+ | $0.20 | 5s |
| Azure DNS | 12+ | $0.50 | 1s |
| GoDaddy | 9 | Incluído | 600s |
| Cloudflare | 15+ | Gratuito* | 60s |
| Hostinger | 9 | Incluído | 600s |

*Cloudflare oferece DNS gratuito ilimitado

---

## Tipos de Registro Comuns

### A (Address)
Mapeia um domínio para um endereço IPv4.
```yaml
type: A
name: www
value: 192.0.2.1
```

### AAAA (IPv6)
Mapeia um domínio para um endereço IPv6.
```yaml
type: AAAA
name: www
value: 2001:db8::1
```

### CNAME (Canonical Name)
Apelido para outro domínio.
```yaml
type: CNAME
name: www
value: @
```

### MX (Mail Exchange)
Servidor de email.
```yaml
type: MX
name: "@"
value: mail.example.com
priority: 10
```

### TXT (Text)
Registro de texto (SPF, DKIM, verificação).
```yaml
type: TXT
name: "@"
value: "v=spf1 include:_spf.google.com ~all"
```

### NS (Name Server)
Servidores DNS autoritativos.
```yaml
type: NS
name: subdomain
value: ns1.example.com
```

---

## Exemplo Multi-Cloud DNS

```yaml
project:
  name: multi-cloud-dns
  environment: production

# DNS primário na AWS
provider:
  name: aws
  region: us-east-1

# DNS secundário no GCP
external_cloudforge:
  providers:
    gcp_dns:
      name: gcp
      region: us-central1
      credentials:
        project_id: ${GCP_PROJECT_ID}

resources:
  # AWS Route53 - Primário
  - type: dns_record
    name: primary-www
    config:
      hosted_zone: Z1234567890ABC
      name: www
      type: A
      value: 192.0.2.1
      ttl: 300

  # GCP Cloud DNS - Secundário
  - type: dns_record
    name: secondary-www
    provider: gcp_dns
    config:
      zone: example-com-zone
      name: www
      type: A
      value: 192.0.2.2
      ttl: 300
```

---

## Comandos Úteis

### Listar providers com DNS
```bash
cloudforge providers | grep dns_record
```

### Ver detalhes do Route53
```bash
cloudforge providers aws
```

### Instalar dependências AWS
```bash
cloudforge install-deps aws
```

### Inicializar projeto DNS
```bash
cloudforge init --provider aws --region us-east-1
```

---

## Dependências por Provider

### AWS
```bash
pip install boto3>=1.34.0
# Route53 já incluído no boto3
```

### GCP
```bash
pip install google-cloud-dns
# Ou todos os serviços GCP
pip install cloudforge[gcp]
```

### Azure
```bash
pip install azure-mgmt-dns
# Ou todos os serviços Azure
pip install cloudforge[azure]
```

### GoDaddy
```bash
pip install requests>=2.31.0
# Incluído no core
```

---

## Próximos Passos

1. **DNS Privado**: Suporte para VPC/VNet private DNS
2. **Health Checks**: Route53 health checks integrados
3. **Traffic Flow**: DNS-based load balancing
4. **GeoDNS**: Roteamento baseado em localização
5. **DNSSEC**: Assinatura automática de zonas

---

**CloudForge Team** - 2026-03-15
Licença: Apache 2.0
