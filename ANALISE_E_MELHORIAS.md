# Análise e Melhorias: CloudForge

O CloudForge é um projeto ambicioso que simplifica a infraestrutura como código (IaC) usando YAML e Python. Após analisar o código-base, implementei uma das funcionalidades mais solicitadas: **Configuração de Chaves Orientada e Segura**.

## 1. Implementação: Guided Setup & Encrypted Vault

Conforme solicitado, implementei o comando `cloudforge configure`. Esta funcionalidade oferece:

- **Instruções Detalhadas**: O sistema indica exatamente onde ir (URLs), quais menus clicar e que opções escolher para obter as API Keys (ex: AWS, GCP, Cloudflare, GoDaddy).
- **Criptografia Local**: Se as variáveis de ambiente não estiverem configuradas, o sistema utiliza um "Vault" local em `.cloudforge/credentials.enc`. Os dados são cifrados usando uma chave derivada de metadados da máquina e do usuário, garantindo que as chaves não fiquem em texto simples.
- **Resolução Automática**: O motor do CloudForge foi atualizado para buscar chaves automaticamente nesse arquivo cifrado se não as encontrar no ambiente.

### Como usar:
```bash
cloudforge configure         # Menu interativo de seleção
cloudforge configure aws     # Configuração direta da AWS
```

## 2. Análise de Melhorias do Projeto

Além do sistema de chaves, identifiquei os seguintes pontos para evolução do CloudForge:

### A. Core & Arquitetura
1.  **Remote State (Estado Remoto)**: Atualmente o estado é um arquivo JSON local. Para uso em equipe, é essencial suportar backends remotos (S3, GCS, Azure Blob) com **State Locking** (via DynamoDB ou similar) para evitar conflitos.
2.  **Arquitetura Pluggable**: O mapeamento de providers está "hardcoded" no CLI e no Engine. Sugiro migrar para um sistema de `plugins` dinâmicos usando `entry_points` do Python, permitindo que a comunidade adicione novos providers sem alterar o core.
3.  **Parallel Execution**: Atualmente o `apply` processa os recursos sequencialmente no grafo. Poderíamos usar `ThreadPullExecutor` para provisionar recursos independentes em paralelo, acelerando significativamente o deploy.

### B. Validação & Segurança
1.  **Semantic Pre-flight**: A validação atual verifica tipos (schema). Podemos adicionar uma fase de "pre-flight" que consulta as APIs dos providers para verificar se IDs (ex: AMIs, Instance Types) realmente existem antes de iniciar o `plan`.
2.  **Native Secrets Integration**: Expandir o sistema de chaves que criei para que o CloudForge possa ler segredos diretamente de serviços de cofre, como **HashiCorp Vault** ou **AWS Secrets Manager**.

### C. Developer Experience (DX)
1.  **Linter/Formatter**: Criar um comando `cloudforge fmt` para auto-formatar os arquivos YAML e `cloudforge lint` para detectar problemas de melhores práticas (ex: recursos sem tags, subnets muito grandes).
2.  **Modules & Reuse**: Implementar suporte a "Módulos" (como no Terraform), permitindo que um arquivo YAML importe definições de outro local, promovendo o reuso de infraestrutura.

---

### Alterações Realizadas:
- [x] Criação de `cloudforge/core/auth.py` (Engine de Criptografia e Guias Interativos)
- [x] Atualização de `cloudforge/core/config.py` (Resolução de variáveis de ambiente + Vault)
- [x] Atualização de `cloudforge/cli.py` (Novo comando `cloudforge configure`)
