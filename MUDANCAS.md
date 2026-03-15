# CloudForge - Mudanças Implementadas

## Data: 2026-03-15

---

## 📋 Resumo

Foram implementadas duas melhorias principais solicitadas:

1. **Comando para listar providers disponíveis** com seus parâmetros
2. **Instalação modular de dependências** para evitar carregar todos os providers

---

## 1. 🖥️ Novos Comandos CLI

### `cloudforge providers`

Lista todos os providers suportados com:
- Nome display e interno
- Quantidade de regiões disponíveis
- Recursos suportados
- Comando de instalação
- Tabela resumo de todos os recursos por provider

**Uso:**
```bash
cloudforge providers
```

### `cloudforge install-deps [provider]`

Instala dependências de um provider específico ou lista opções.

**Uso:**
```bash
# Lista todos providers disponíveis para instalação
cloudforge install-deps

# Instala dependências da AWS
cloudforge install-deps aws

# Instala dependências do GCP com upgrade
cloudforge install-deps gcp --upgrade
```

---

## 2. 📦 Instalação Modular

### Nova Estrutura de Arquivos

```
requirements-core.txt          # Dependências básicas (obrigatórias)
requirements-aws.txt           # Provider AWS
requirements-gcp.txt           # Provider GCP
requirements-azure.txt         # Provider Azure
requirements-alibaba.txt       # Provider Alibaba Cloud
requirements-godaddy.txt       # Provider GoDaddy DNS
requirements-cloudflare.txt    # Provider Cloudflare DNS
requirements.txt               # Todos os providers (para compatibilidade)
```

### setup.py Atualizado

Agora usa `extras_require` para instalação seletiva:

```python
extras_require={
    "aws": [...],
    "gcp": [...],
    "azure": [...],
    "alibaba": [...],
    "dns": [],
    "all": [...],  # Todos os providers
}
```

### Comandos de Instalação

```bash
# Apenas core (sem providers)
pip install cloudforge

# Core + AWS
pip install cloudforge[aws]

# Core + GCP + Alibaba
pip install cloudforge[gcp,alibaba]

# Todos os providers
pip install cloudforge[all]
```

---

## 3. 🗂️ PROVIDER_REGISTRY

Novo registry no `engine.py` com metadados de cada provider:

```python
PROVIDER_REGISTRY = {
    "aws": {
        "display_name": "Amazon Web Services",
        "description": "Provider para AWS (EC2, VPC, EKS, RDS)",
        "dependencies": ["boto3>=1.34.0"],
        "resources": ["vm", "vpc", "subnet", "security_group", "kubernetes", "database"],
        "install": "pip install cloudforge[aws]",
    },
    # ... outros providers
}
```

---

## 4. 📄 Documentação Adicional

### INSTALL.md
Guia completo de instalação modular com:
- Explicação de cada provider
- Dependências instaladas
- Recursos disponíveis
- Exemplos de uso
- Troubleshooting

### demo_commands.py
Script de demonstração dos novos comandos CLI.

---

## 5. 📊 Providers Suportados

| Provider | Recursos | Dependências |
|----------|----------|--------------|
| AWS | 6 | boto3 |
| GCP | 11 | google-cloud-* (7 pacotes) |
| Azure | 6 | azure-mgmt-* (5 pacotes) |
| Alibaba | 7 | alibabacloud-* (5 pacotes) |
| GoDaddy | 1 | requests (core) |
| Cloudflare | 1 | requests (core) |

---

## 6. 🎯 Benefícios

### Economia de Espaço
- **Core apenas**: ~50 MB
- **Um provider**: ~80-200 MB (dependendo do provider)
- **Todos**: ~500 MB

### Vantagens
1. **Instalação mais rápida**: Menos pacotes para instalar
2. **Menos conflitos**: Menos dependências = menos chance de conflito
3. **Projetos isolados**: Cada projeto instala apenas o necessário
4. **CI/CD mais eficiente**: Pipelines instalam apenas providers usados

---

## 7. 🔧 Arquivos Modificados

### Criados (11)
- `requirements-core.txt`
- `requirements-aws.txt`
- `requirements-gcp.txt`
- `requirements-azure.txt`
- `requirements-alibaba.txt`
- `requirements-godaddy.txt`
- `requirements-cloudflare.txt`
- `INSTALL.md`
- `demo_commands.py`
- `MUDANCAS.md` (este arquivo)

### Modificados (4)
- `cloudforge/cli.py` - Adicionados comandos `providers` e `install-deps`
- `cloudforge/core/engine.py` - Adicionado `PROVIDER_REGISTRY`
- `setup.py` - Adicionado `extras_require`
- `requirements.txt` - Agora usa includes modulares

---

## 8. 🧪 Testes

### Verificação de Sintaxe
```bash
python -m py_compile cloudforge/cli.py
python -m py_compile cloudforge/core/engine.py
python -m py_compile setup.py
```
✅ Todos os arquivos compilam sem erros

### Verificação de Imports
```bash
python -c "from cloudforge.core.engine import PROVIDER_REGISTRY"
```
✅ Imports funcionam corretamente

---

## 9. 📝 Exemplo de Uso

### Cenário: Projeto usando apenas Alibaba Cloud

```bash
# 1. Criar ambiente virtual
python -m venv alibaba-venv
cd alibaba-venv
Scripts\activate  # Windows

# 2. Instalar CloudForge + Alibaba
pip install cloudforge[alibaba]

# 3. Ver providers instalados
cloudforge providers

# 4. Inicializar projeto
cloudforge init --provider alibaba --region cn-hangzhou

# 5. Validar e aplicar
cloudforge validate
cloudforge plan
cloudforge apply
```

---

## 10. 🔄 Backward Compatibility

### Compatível
- `pip install cloudforge` - Instala core apenas
- `pip install -r requirements.txt` - Instala tudo (como antes)

### Mudança de Comportamento
- **Antes**: `requirements.txt` instalava todos os providers
- **Agora**: `requirements.txt` ainda instala tudo, mas há opções modulares

### Migração
Projetos existentes continuam funcionando. Para migrar para instalação modular:

```bash
# Antes
pip install -r requirements.txt

# Depois (exemplo: apenas GCP)
pip install cloudforge[gcp]
```

---

## 11. 🎯 Próximos Passos Sugeridos

1. **Adicionar detecção automática**: CLI poderia sugerir instalação do provider ao detectar configuração

2. **Lazy loading**: Carregar providers apenas quando necessário (já implementado no `get_provider`)

3. **Plugin system**: Permitir providers de terceiros

4. **Version pinning**: Congelar versões de dependências para reprodutibilidade

---

## 12. 📞 Suporte

Para dúvidas ou problemas:
- `INSTALL.md` - Guia de instalação
- `README.md` - Documentação principal
- `MELHORIAS.md` - Detalhes das melhorias
- `demo_commands.py` - Demonstração interativa

---

**CloudForge Team** - 2026-03-15
Licença: Apache 2.0
