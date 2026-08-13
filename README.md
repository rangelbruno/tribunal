# Tribunal 2.0

Aplicação local em Streamlit para assinar PDFs com certificado digital A3, dividir PDFs, extrair arquivos ZIP, executar OCR e transformar PDFs digitalizados em PDFs pesquisáveis.

## Pré-requisitos

- Windows 10 ou 11;
- Python 3.14 instalado;
- driver do token/certificado digital A3 instalado;
- token conectado ao computador;
- acesso à internet durante a instalação das dependências e no primeiro uso do OCR.
- **opcional, mas muito recomendado:** Tesseract OCR instalado (veja abaixo).

## Tesseract OCR (deixa o PDF pesquisável várias vezes mais rápido)

A página **PDF Pesquisável (Lote)** funciona sem nenhuma instalação extra, mas
nesse caso usa o EasyOCR, que é lento e processa uma página por vez. Com o
Tesseract instalado, o app o detecta sozinho e passa a processar várias páginas
em paralelo.

### Windows

1. Baixe o instalador em <https://github.com/UB-Mannheim/tesseract/wiki>.
2. Durante a instalação, em *Additional language data*, marque **Portuguese**.
3. Conclua a instalação e reinicie o app.

O app procura o Tesseract no PATH e nos caminhos padrão de instalação. Se você
instalou em outro lugar, defina a variável de ambiente `TESSERACT_CMD` com o
caminho completo do `tesseract.exe`.

### Linux

```bash
sudo dnf install tesseract tesseract-langpack-por   # Fedora
sudo apt install tesseract-ocr tesseract-ocr-por    # Debian/Ubuntu
```

A própria página avisa qual motor está ativo assim que é aberta.

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

## PDF Pesquisável em lote

Na página **PDF Pesquisável (Lote)**:

1. Envie quantos PDFs digitalizados quiser de uma vez.
2. Ajuste as opções, se necessário, e clique em **Gerar PDFs pesquisáveis**.
3. Baixe os arquivos um a um ou todos de uma vez em um ZIP.

O PDF de saída continua idêntico na tela — o texto reconhecido entra em uma
camada invisível por cima da imagem, de modo que o `Ctrl+F` passa a encontrar o
conteúdo e o texto pode ser copiado.

As opções que mais afetam o tempo de processamento:

- **Pular páginas que já têm texto**: mantenha marcado. Peças geradas por sistema
  já são pesquisáveis e não precisam de OCR — costuma ser o maior ganho.
- **Qualidade da leitura**: 200 DPI atende à maioria dos documentos. Use 300 DPI
  apenas em digitalizações ruins ou com letra miúda.
- **Páginas em paralelo**: só aparece com o Tesseract instalado.

Reprocessar um arquivo já pesquisável não faz nada além de copiá-lo, então não
há risco em passar o lote inteiro de novo.

## Problemas comuns

- **`No module named 'pkcs11'`**: execute `python -m pip install python-pkcs11`.
- **Nenhum certificado encontrado**: confirme se o token está conectado, se o driver está instalado e se o caminho da DLL PKCS#11 está correto.
- **OCR demorando no primeiro uso**: o EasyOCR precisa baixar os modelos de reconhecimento. Aguarde o término do download.
- **PDF pesquisável muito lento**: a página está usando o EasyOCR. Instale o Tesseract (seção acima) e reinicie o app.
- **Tesseract instalado mas não detectado**: defina `TESSERACT_CMD` com o caminho completo do executável e reinicie o app.
- **Texto reconhecido com erros**: aumente a qualidade da leitura para 300 DPI. Digitalizações tortas ou com pouco contraste limitam o que qualquer OCR consegue ler.
- **Porta 8501 em uso**: encerre outra instância do Streamlit ou inicie em outra porta com `python -m streamlit run app.py --server.port 8502`.

Para encerrar a aplicação, volte ao terminal e pressione `Ctrl+C`.
