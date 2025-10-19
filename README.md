# LCSC QR Parts Importer

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg) ![License](https://img.shields.io/badge/License-MIT-green.svg) ![Status](https://img.shields.io/badge/Status-Experimental-orange.svg)

Um utilitário Python para capturar informações de componentes eletrônicos a partir de QR Codes impressos ou digitais da **LCSC**, enriquecer com dados do site da LCSC e enviar automaticamente para o **PartsBox**, incluindo a criação do componente e adição de estoque.

Este projeto é útil para empresas, makers e engenheiros que precisam automatizar o inventário de componentes e reduzir a entrada manual de dados.

**Observação:**  
Para melhor qualidade de leitura de QR Codes, é recomendado usar o celular como webcam via apps como **Camo** ou outro programa de captura, possivelmente junto com o **OBS**, pois melhora significativamente a nitidez da imagem e facilita a identificação dos QR Codes. Isso caso não tenha uma webcam de boa qualidade.
---

## Funcionalidades

- **Leitura de QR Codes** através de webcam.
- **Parsing de dados do QR Code** no formato esperado (`pc`, `pm`, `qty`, etc.).
- **Scraping de informações adicionais do LCSC**:
  - Fabricante
  - Número de peça do fabricante
  - Pacote/Footprint
  - Descrição
  - Preço unitário
- **Envio automático para PartsBox**:
  - Criação do componente local
  - Adição de estoque no storage especificado
- **Interface de progresso visual** na webcam mostrando QR Codes detectados.
- **Salvamento local de dados** em JSON para conferência ou reenvio.

---

## Pré-requisitos

- Python 3.11 ou superior  
- Conta PartsBox com API Key válida  
- Webcam conectada ao computador  

### Bibliotecas Python necessárias

```bash
pip install -r requirements.txt
```

Conteúdo sugerido para `requirements.txt`:

```
opencv-python>=4.7.0
numpy>=1.26.0
pyzbar>=0.1.9
requests>=2.31.0
beautifulsoup4>=4.12.2
```

---

## Como usar

1. Clone o repositório:

```bash
git clone https://github.com/issacarbrun/qrcode_lcsc_partsbox.git
cd lcsc-qr-parts-importer
```

2. Configure seu **API Key do PartsBox** e o **Storage ID** no arquivo `main.py`:

```python
PARTSBOX_API_KEY = "sua_api_key"
STORAGE_ID = "id_do_storage_real"
```

3. Execute o script:

```bash
python main.py
```

4. Use o menu interativo:

```
1 - Ler QR Code e salvar localmente
2 - Enviar todas as partes para PartsBox
3 - Sair
```

- Ao escolher **1**, a webcam abrirá e exibirá mensagens de status:
  - Procurando QR Code
  - QR Code detectado (pressione `c` para confirmar)
- Ao escolher **2**, todas as partes salvas serão enviadas, com progresso de envio mostrado no terminal.

---

## Estrutura do JSON salvo (`parts_to_send.json`)

```json
[
  {
    "pbn": "PICK2509250004",
    "on": "GB2509240149",
    "pc": "C2918361",
    "pm": "RVT1E221M0607",
    "qty": "40",
    "manufacturer": "ROQANG",
    "package": "SMD,D6.3xL7.7mm",
    "description": "220uF 25V ±20% 150mA@120Hz SMD,D6.3xL7.7mm Aluminum Electrolytic Capacitors ROHS",
    "unit_price": 0.0305
  }
]
```

## Contribuição

Contribuições são bem-vindas!  
- Abra uma issue se encontrar bugs ou tiver sugestões.  
- Faça um fork e envie pull requests com melhorias.  

---

## Licença

Este projeto é **open source** sob a licença **MIT**.
