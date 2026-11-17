# gerar_placas.py
import os
import qrcode

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
QR_DIR = os.path.join(BASE_DIR, "static", "qrcodes")
os.makedirs(QR_DIR, exist_ok=True)

# Dicionário limpo de tokens dos PEVs
PEVS = {
    "ECO-SALA-01": "PEV Sala de Aula - Teste",
    "ECO-CEAGRI-01": "CEAGRI Central",
    "ECO-BSI-02": "BSI Informática",
    "ECO-RU-03": "Restaurante Universitário",
    "ECO-ZOO-04": "Zootecnia"
}

for raw_token, nome in PEVS.items():
    # Remove qualquer caractere ou espaço invisível acidental
    token = raw_token.strip()
    
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=3
    )
    qr.add_data(token)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1B3624", back_color="#FFFFFF")
    caminho = os.path.join(QR_DIR, f"{token}.png")
    img.save(caminho)
    print(f"Salvo com sucesso: {caminho}")

print("\nTodos os QR Codes foram criados em static/qrcodes/ sem erros!")