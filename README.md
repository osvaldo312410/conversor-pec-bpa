CONVERSOR PEC BPA - Sistema de Conversão de Dados
📋 Descrição do Sistema
O CONVERSOR PEC BPA é um sistema desenvolvido em Python/Flask para conversão e processamento de dados do Prontuário Eletrônico do Cidadão (PEC) para o formato BPA (Boletim de Produção Ambulatorial) do DATASUS.

✨ Funcionalidades Principais
🔄 Conversão de Dados
Extração de dados do PostgreSQL (PEC)

Transformação para formato BPA

Geração de arquivos TXT no padrão DATASUS

Configuração de procedimentos, CIDs e serviços

📊 Gerenciamento de Dados
Interface web para visualização de dados

Paginação e filtros de registros

Configuração de procedimentos válidos

Gestão de dados municipais

🔧 Ferramentas Auxiliares
Download automático do BDSIA via FTP

Conversão de arquivos DBF para SQLite

Configuração de conexão com banco PostgreSQL

Sistema de bloqueio por data

🛠 Tecnologias Utilizadas
Backend: Python, Flask

Frontend: HTML, JavaScript, CSS

Banco de Dados: SQLite, PostgreSQL

Interface Desktop: WebView

Processamento: Threading para operações assíncronas

📦 Estrutura do Projeto
text
conversor-pec-bpa/
├── app.py                 # Aplicação principal Flask
├── templates/            # Templates HTML
├── static/              # Arquivos estáticos (CSS, JS)
├── bdsia/               # Arquivos do BDSIA
├── config.json          # Configurações de conexão
└── bdsia.sqlite         # Banco SQLite local
🚀 Instalação e Execução
Pré-requisitos
Python 3.7+

PostgreSQL (para conexão com PEC)

Dependências Python listadas no requirements.txt

Instalação
Clone o repositório:

bash
git clone [url-do-repositorio]
cd conversor-pec-bpa
Instale as dependências:

bash
pip install -r requirements.txt
Execute o sistema:

bash
python app.py
Dependências Principais
python
flask
psycopg2-binary
dbfread
pywebview
📖 Guia de Uso
1. Configuração Inicial
Configuração do Banco PostgreSQL:

Acesse a seção "Conecta PEC"

Configure host, database, usuário, senha e porta

Teste a conexão antes de prosseguir

Dados do Município:

Configure os dados municipais na seção específica

Inclua nome, sigla, CNES, CNPJ e código IBGE

2. Download do BDSIA
Acesse "Download BDSIA"

Informe a competência (formato AAAAMM)

Aguarde o download e instalação automática

Converta os arquivos DBF para SQLite

3. Processamento de Dados
Extrair dados do PEC:

Acesse "Processar Produção"

Informe competência e CNES (opcional)

Execute a extração

Configurar Procedimentos:

Acesse "Configuração de Procedimentos"

Associe CIDs e serviços aos procedimentos

Valide os mapeamentos

Exportar BPA:

Gere arquivo TXT no formato BPA

Download automático para pasta Downloads

🔧 Configurações
Bloqueio por Data
O sistema possui mecanismo de bloqueio automático:

Data limite configurável

Pode ser desativado alterando BLOQUEIO_ATIVADO = False

Conexão FTP
Host: arpoador.datasus.gov.br

Diretório: /siasus/sia

Download automático de arquivos BDSIA

📊 Estrutura de Dados
Tabelas Principais
tb_fat_prod: Dados convertidos para BPA

Campos: identificação, procedimentos, dados do paciente

Relacionamento com tabelas de configuração

tb_config_proced: Configuração de procedimentos

Mapeamento de CIDs e serviços

Classificações específicas

tb_dados_municipio: Dados municipais

Informações para cabeçalho do BPA

⚠️ Considerações Importantes
Segurança
Configurações sensíveis em arquivo separado

Bloqueio por data para controle de uso

Validação de dados de entrada

Performance
Processamento em threads separadas

Paginação para grandes volumes de dados

Operações assíncronas para downloads

Compatibilidade
Testado em Windows com PostgreSQL

Interface web responsiva

Suporte a caracteres especiais

🆘 Solução de Problemas
Conexão com PostgreSQL
Verifique as credenciais no config.json

Teste a conexão antes do processamento

Confirme permissões de acesso

Download BDSIA
Verifique conexão com internet

Confirme competência válida

Espaço em disco suficiente

Exportação BPA
Valide configurações municipais

Confirme mapeamento de procedimentos

Verifique permissões de escrita

📞 Suporte
Para issues e dúvidas:

Verifique logs da aplicação

Confirme configurações do banco

Valide formato dos dados de entrada

📄 Licença
Livre

Versão: 1.0
Última atualização: [Data]
Compatível com: PEC [Versão], BPA [Versão]
