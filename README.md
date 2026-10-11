# Ecoflux (UFRPE)

Protótipo mobile-first de descarte inteligente e gamificação ecológica para a Universidade Federal Rural de Pernambuco.

## Tecnologias Empregadas
- **Backend:** Python 3 + Flask (sem APIs pagas de mapas ou tokens).
- **Banco de Dados:** SQLite nativo com auto-inicialização (`database.db`).
- **Segurança:** Hashing via `bcrypt` e proteção de brute-force na rota de login (3 falhas acionam bloqueio de 30 segundos).
- **Frontend:** HTML5 semântico, Leaflet.js + OpenStreetMap (via CDN) e HTML5-QRCode.
- **Validação Espacial:** Cálculo geodésico via Haversine no servidor para travar descartes fora de um raio de 30 metros dos PEVs.

## Execução Local

1. Garanta que o Python 3.9+ esteja instalado em seu ambiente.
2. Clone ou crie a estrutura de diretórios do projeto e navegue até a raiz:
   ```bash
   cd Ecoflux