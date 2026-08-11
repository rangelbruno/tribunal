# Tribunal 2.0

Aplicação local em Streamlit para assinar PDFs com certificado digital A3, dividir PDFs, extrair arquivos ZIP e executar OCR.

## Pré-requisitos

- Windows 10 ou 11;
- Python 3.14 instalado;
- driver do token/certificado digital A3 instalado;
- token conectado ao computador;
- acesso à internet durante a instalação das dependências e no primeiro uso do OCR.

## Instalação

Abra o Prompt de Comando ou PowerShell na pasta do projeto e execute:

```powershell
python -m pip install -r requirements.txt
```

Se o comando `python` não for encontrado, instale o Python e marque a opção **Add Python to PATH** durante a instalação.

## Como iniciar

Execute no terminal, dentro da pasta do projeto:

```powershell
python -m streamlit run app.py
```

Depois, acesse no navegador:

<http://localhost:8501>

No Windows, também é possível abrir o arquivo **Iniciar Assinador.bat**. Esse arquivo espera que o Python esteja instalado em `C:\Python314\python.exe`. Se o Python estiver em outro local, use o comando acima ou ajuste o caminho no arquivo `.bat`.

### Linux ou macOS

O script de inicialização cria o ambiente virtual, instala as dependências necessárias e inicia o projeto automaticamente:

```bash
./start.sh
```

Na primeira execução, a instalação pode demorar alguns minutos. Nas próximas, o projeto será iniciado diretamente, exceto quando o `requirements.txt` for alterado.

## Configuração do certificado A3

Na página **Tribunal 2.0**:

1. Informe o caminho da DLL PKCS#11 do driver do token. O valor padrão é `C:\Windows\System32\aetpkss1.dll`.
2. Informe o PIN do token.
3. Selecione o certificado encontrado.
4. Escolha o tipo de assinatura e envie os PDFs.

O nome e o caminho da DLL podem variar conforme o fabricante do token. Consulte o software ou o suporte do certificado caso a DLL não seja encontrada.

## Problemas comuns

- **`No module named 'pkcs11'`**: execute `python -m pip install python-pkcs11`.
- **Nenhum certificado encontrado**: confirme se o token está conectado, se o driver está instalado e se o caminho da DLL PKCS#11 está correto.
- **OCR demorando no primeiro uso**: o EasyOCR precisa baixar os modelos de reconhecimento. Aguarde o término do download.
- **Porta 8501 em uso**: encerre outra instância do Streamlit ou inicie em outra porta com `python -m streamlit run app.py --server.port 8502`.

Para encerrar a aplicação, volte ao terminal e pressione `Ctrl+C`.
