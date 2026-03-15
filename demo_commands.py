#!/usr/bin/env python3
"""
CloudForge - Demonstração dos Novos Comandos CLI

Este script demonstra como usar os novos comandos:
- cloudforge providers
- cloudforge install-deps
"""

import subprocess
import sys


def run_command(cmd: str):
    """Executa um comando e mostra o resultado."""
    print(f"\n{'='*60}")
    print(f"Executando: {cmd}")
    print('='*60)
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=r"C:\prj\cloudforge"
    )
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("ERROS:", result.stderr)
    
    return result.returncode


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║        CloudForge - Demonstração de Comandos CLI          ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 1. Mostrar help do CLI
    run_command("python -m cloudforge.cli --help")
    
    # 2. Listar providers disponíveis
    print("\n" + "📦" * 30)
    print("COMANDO: cloudforge providers")
    print("📦" * 30)
    run_command("python -m cloudforge.cli providers")
    
    # 3. Mostrar install-deps sem argumentos
    print("\n" + "🔧" * 30)
    print("COMANDO: cloudforge install-deps (sem argumentos)")
    print("🔧" * 30)
    run_command("python -m cloudforge.cli install-deps")
    
    # 4. Mostrar install-deps para um provider específico
    print("\n" + "🔧" * 30)
    print("COMANDO: cloudforge install-deps aws")
    print("🔧" * 30)
    run_command("python -m cloudforge.cli install-deps aws")
    
    # 5. Mostrar install-deps para provider inválido
    print("\n" + "⚠️" * 30)
    print("COMANDO: cloudforge install-deps invalid-provider")
    print("⚠️" * 30)
    run_command("python -m cloudforge.cli install-deps invalid-provider")
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║                    Demonstração Finalizada                ║
╚═══════════════════════════════════════════════════════════╝

📚 Resumo dos Comandos:

1. cloudforge providers
   → Lista todos os providers disponíveis com suas informações

2. cloudforge install-deps
   → Lista opções de instalação de dependências

3. cloudforge install-deps <provider>
   → Instala dependências de um provider específico
   → Exemplos: aws, gcp, azure, alibaba

4. cloudforge install-deps <provider> --upgrade
   → Faz upgrade das dependências existentes

📖 Para mais informações, consulte:
   - README.md
   - INSTALL.md
   - MELHORIAS.md
    """)


if __name__ == "__main__":
    main()
