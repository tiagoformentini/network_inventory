# network_inventory
Sistema para varrer a rede a rede local, coletar dados de máquinas Windows
via WMI remoto (RAM, disco, interfaces de rede, chave do produto, CPU, etc.)
e exibir tudo em um dashboard web.
**Use apenas em redes que você administra e tem autorização para
inventariar.** A varredura usa credenciais administrativas para se conectar
remotamente em cada máquina que deve estar vinculadas a um servidor de dominio do
Windows Server 2016 ou posterior.

## Requisitos

### No computador que vai rodar o Flask (o "servidor")
- **Precisa ser Windows** (a biblioteca `wmi` depende de `pywin32`/DCOM, que só
  funciona no Windows).
- Python 3.9+
- Instalar dependências:
  ```
  pip install -r requirements.txt
  ```

### Nas máquinas-alvo (as que serão inventariadas)
Para o WMI remoto funcionar, cada máquina precisa:
1. Ter o **WMI remoto habilitado** — normalmente já vem habilitado, mas
   confira em `Painel de Controle > Ferramentas Administrativas > Serviços de
   Componentes > WMI Control`.
2. Ter a regra de firewall **"Windows Management Instrumentation (WMI)"**
   habilitada (entrada), ou liberar as portas:
   - TCP 135 (RPC Endpoint Mapper)
   - Faixa dinâmica de portas RPC (ou fixar uma faixa via GPO)
3. Estar acessível na rede (sem bloqueios de firewall entre o servidor e a
   máquina-alvo).
4. Você precisa ter uma **conta com privilégio administrativo** local ou de
   domínio nessas máquinas.

Se as máquinas estiverem em um domínio Active Directory, isso costuma já
funcionar de fábrica para o usuário Domain Admin. Se forem máquinas fora de
domínio (grupo de trabalho), pode ser necessário ajustar `LocalAccountTokenFilterPolicy`
no registro para permitir que contas administrativas locais façam WMI remoto.

## Como rodar

```bash
pip install -r requirements.txt
python app.py
```

Acesse `http://localhost:5000` no navegador.

Na tela inicial:
1. Preencha a rede (já vem `10.0.33.0/24` por padrão).
2. Informe domínio (opcional, se as máquinas forem de domínio),
   usuário e senha administrativos.
3. Clique em "Iniciar varredura". O sistema faz um ping sweep para achar
   hosts ativos e depois coleta informações via WMI de cada um.
4. O dashboard mostra um card por máquina; clique em "Ver detalhes" para
   ver discos, interfaces de rede e a chave do Windows completos.

## Monitor de status (online/offline)

O status online/offline de cada máquina **não depende mais de qual rede você
escaneou por último**. Assim que a aplicação sobe, uma thread em background
(`monitor.py`) fica pingando, a cada 15 segundos (ajustável via variável de
ambiente `PING_INTERVAL_SECONDS`), **todas** as máquinas já cadastradas no
banco, não importa o range/CIDR usado na última varredura WMI:

- Se uma máquina responde ao ping → fica/permanece `online`.
- Se para de responder → fica `offline`.
- Se uma máquina que estava `offline` volta a responder → volta a ficar
  `online` automaticamente.

A varredura WMI (botão "Iniciar varredura") continua servindo só para
**coletar informações detalhadas** (RAM, disco, chave do Windows etc.) de um
range específico — ela não derruba mais o status de máquinas fora desse
range. O dashboard já atualiza os badges de status sozinho a cada 10
segundos, sem precisar recarregar a página ou rodar uma nova varredura.

## Estrutura do projeto

```
network_inventory/
├── app.py                # Aplicação Flask (rotas, dashboard, scan em background)
├── scanner.py             # Ping sweep (rede inteira e lista específica de IPs)
├── wmi_collector.py        # Coleta via WMI remoto (RAM, disco, rede, chave do Windows)
├── monitor.py               # Monitor contínuo de ping (mantém online/offline atualizado)
├── database.py             # Persistência em SQLite (inventory.db, criado automaticamente)
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   └── machine_detail.html
└── requirements.txt
```

## Segurança e boas práticas

- As credenciais informadas no formulário são usadas apenas em memória
  durante a varredura e não são persistidas em disco.
- Troque o `app.secret_key` em `app.py` antes de usar em produção.
- Considere rodar isso apenas em uma rede interna/administrativa e não expor
  a porta 5000 publicamente, já que o dashboard mostra chaves de produto do
  Windows.
- Para redes grandes, ajuste `max_workers` em `scanner.py` conforme
  necessário.

## Limitações conhecidas

- Funciona apenas com máquinas Windows (usa WMI).
- O servidor Flask precisa rodar em uma máquina Windows.
- Firewalls e políticas de grupo restritivas podem bloquear o WMI remoto —
  nesse caso, os erros aparecem na tela do dashboard após a varredura
