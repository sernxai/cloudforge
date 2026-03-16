# CloudForge - Comando Providers

## Visão Geral

O comando `cloudforge providers` foi melhorado para fornecer informações detalhadas sobre todos os providers suportados.

## Comandos Disponíveis

### 1. Listar Todos os Providers

```bash
cloudforge providers
```

**Saída:**
- Tabela com todos os 11 providers
- Nome do provider
- Nome interno (para uso no CLI)
- Número de regiões disponíveis
- Lista completa de recursos suportados

### 2. Ver Detalhes de um Provider Específico

```bash
cloudforge providers <nome>
```

**Exemplos:**
```bash
cloudforge providers aws          # Detalhes da AWS
cloudforge providers oracle       # Detalhes do Oracle Cloud
cloudforge providers locaweb      # Detalhes da Locaweb
cloudforge providers digitalocean # Detalhes da DigitalOcean
cloudforge providers hetzner      # Detalhes da Hetzner
cloudforge providers hostinger    # Detalhes da Hostinger
cloudforge providers gcp          # Detalhes do GCP
cloudforge providers azure        # Detalhes do Azure
cloudforge providers alibaba      # Detalhes do Alibaba
cloudforge providers godaddy      # Detalhes da GoDaddy
cloudflare providers cloudflare   # Detalhes da Cloudflare
```

**Saída:**
- Nome completo e descrição
- Total de regiões e recursos
- Lista completa de regiões agrupadas por continente
- Lista de recursos com descrição
- Dependências necessárias
- Comandos úteis para iniciar

## Exemplo de Saída - Detalhes da Locaweb

```
============================================================
Locaweb Cloud
============================================================

  Nome Interno:     locaweb
  Descricao:        Provider para Locaweb (Simple Server, Redes, LB, Hospedagem)
  Total Regioes:    2
  Total Recursos:   7

Regioes Disponíveis:

  BR:
    • br-nordeste
    • br-sudeste

Recursos Suportados:
  ✓ vm                   Maquinas Virtuais (Compute)
  ✓ vpc                  Rede Virtual (VPC/VNet)
  ✓ subnet               Sub-redes
  ✓ security_group       Firewall / Security Group
  ✓ lb                   Load Balancer
  ✓ website              Hospedagem de Sites
  ✓ database             Banco de Dados Gerenciado

Dependencias:
  • requests>=2.31.0

Comandos Úteis:
  cloudforge init --provider locaweb --region br-sudeste
  cloudforge install-deps locaweb
```

## Exemplo de Saída - Oracle Cloud

O Oracle Cloud tem 27 regiões distribuídas em:

- **Africa**: af-johannesburg-1
- **Asia-Pacifico**: 9 regiões (Sydney, Tokyo, Seoul, etc.)
- **Canada**: ca-toronto-1
- **China**: cn-chengdu-1
- **Europa**: 7 regiões (Frankfurt, London, Paris, etc.)
- **Oriente Medio**: 3 regiões (Dubai, Jeddah, Riyadh)
- **America do Sul**: sa-saopaulo-1, sa-vinhedo-1
- **Estados Unidos**: 3 regiões (Phoenix, Ashburn, San Jose)

## Providers Suportados

| # | Provider | Regiões | Recursos |
|---|----------|---------|----------|
| 1 | AWS | 10 | 6 |
| 2 | GCP | 8 | 11 |
| 3 | Azure | 10 | 6 |
| 4 | Alibaba | 18 | 7 |
| 5 | Oracle | 27 | 7 |
| 6 | DigitalOcean | 14 | 7 |
| 7 | Hetzner | 3 | 5 |
| 8 | Hostinger | 8 | 4 |
| 9 | Locaweb | 2 | 7 |
| 10 | GoDaddy | 1 | 1 |
| 11 | Cloudflare | 1 | 1 |

**Total: 11 providers, ~103 regiões, ~60 recursos diferentes**

## Melhorias Implementadas

1. **Tabela resumo mais limpa**
   - Coluna "Instalação" removida
   - Recursos mostrados completos (não truncados)
   - Linhas separadas para melhor leitura

2. **Detalhes por provider**
   - Regiões agrupadas por continente/região geográfica
   - Recursos com descrição
   - Dependências listadas
   - Comandos úteis prontos para copiar

3. **Comando com argumento**
   - `cloudforge providers` - lista todos
   - `cloudforge providers <nome>` - detalhes de um

## Próximos Passos

- Adicionar opção `--json` para saída em formato JSON
- Adicionar opção `--region` para filtrar por região
- Adicionar comparação entre providers

---

**CloudForge Team** - 2026-03-15
Licença: Apache 2.0
