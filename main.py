import cv2
import json
import requests
import numpy as np
from bs4 import BeautifulSoup
from pathlib import Path
from pyzbar.pyzbar import decode, ZBarSymbol

# === CONFIGURAÇÕES ===
PARTSBOX_API_KEY = ""
PARTSBOX_BASE_URL = "https://api.partsbox.com/api/1"
DATA_FILE = Path("parts_to_send.json")
STORAGE_ID = ""  # Coloque seu storage real

# === FUNÇÕES AUXILIARES ===
def parse_qr_data(qr_text):
    qr_text = qr_text.strip("{}[]")
    data = {}
    for item in qr_text.split(","):
        if ":" in item:
            k, v = item.split(":", 1)
            data[k.strip()] = v.strip().strip('"') or None
    return data if "pc" in data else None

def load_data():
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# === SCRAPING LCSC ===
def get_lcsc_info(pc):
    url = f"https://www.lcsc.com/product-detail/{pc}.html?s_z=n_{pc}^"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200: return {}

    soup = BeautifulSoup(response.text, "html.parser")
    info = {}
    for row in soup.select("table tr"):
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 2:
            key, value = cols[0], cols[1]
            if "Manufacturer" in key: info["manufacturer"] = value
            elif "Mfr. Part" in key: info["mfr_part_number"] = value
            elif "Package" in key: info["package"] = value
            elif "Description" in key: info["description"] = value

    # Captura unit price da tabela de preços
    price_row = soup.select_one("table.priceTable tbody tr.major2--text")
    if price_row:
        try:
            price_text = price_row.select("td")[1].get_text(strip=True).replace("$", "").replace(",", "")
            info["unit_price"] = float(price_text)
        except: info["unit_price"] = None

    if "description" not in info:
        desc_tag = soup.find("meta", {"name": "description"})
        if desc_tag: info["description"] = desc_tag.get("content")
    return info

# === ENVIO PARA PARTSBOX ===
def send_to_partsbox(part):
    headers = {"Authorization": f"Token {PARTSBOX_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "part/type": "local",
        "part/name": part.get("mfr_part_number") or part.get("pm"),
        "part/description": part.get("description") or f"LCSC {part.get('pc')}",
        "part/footprint": part.get("package") or "Unknown",
        "part/manufacturer": part.get("manufacturer") or "Unknown",
        "part/mpn": part.get("mfr_part_number") or "Unknown",
        "part/notes": f"LCSC code: {part.get('pc')}\nManufacturer: {part.get('manufacturer')}\nPackage: {part.get('package')}",
        "part/tags": ["imported", "lcsc"]
    }
    resp = requests.post(f"{PARTSBOX_BASE_URL}/part/create", headers=headers, json=payload)
    if resp.status_code not in (200, 201): return None

    part_id = resp.json().get("data", {}).get("part/id")
    if part_id and part.get("qty") and part["qty"].isdigit():
        add_stock_to_partsbox(part_id, part["qty"], part)
    return part_id

def add_stock_to_partsbox(part_id, qty, part):
    headers = {"Authorization": f"Token {PARTSBOX_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "stock/part-id": part_id,
        "stock/storage-id": STORAGE_ID,
        "stock/quantity": int(qty),
        "stock/comments": "Initial import from LCSC QR"
    }
    if part.get("unit_price"): 
        payload["stock/price"] = float(part["unit_price"])
        payload["stock/currency"] = "usd"
    requests.post(f"{PARTSBOX_BASE_URL}/stock/add", headers=headers, json=payload)

# === LEITOR DE QR CODE ===
def scan_qr():
    cap = cv2.VideoCapture(1)
    qr_lidos, qr_nao_confirmados = set(), {}

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Aviso de status na tela
        status_text = "Procurando QR Code..." if not qr_nao_confirmados else "QR detectado! Pressione 'c' para confirmar."
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        decoded_objects = decode(frame, symbols=[ZBarSymbol.QRCODE])
        for obj in decoded_objects:
            data = obj.data.decode("utf-8").strip()
            if not data or data in qr_lidos: continue
            if data not in qr_nao_confirmados:
                qr_nao_confirmados[data] = 0

            pts = obj.polygon
            if len(pts) > 4: pts = cv2.convexHull(np.array(pts, dtype=np.int32)).reshape(-1, 2)
            for j in range(len(pts)):
                cv2.line(frame, tuple(pts[j]), tuple(pts[(j+1)%len(pts)]), (0,255,0), 2)

        cv2.imshow("Leitor QR Code", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"): break
        elif key == ord("c") and qr_nao_confirmados:
            data_confirmado = next(iter(qr_nao_confirmados))
            parsed = parse_qr_data(data_confirmado)
            if parsed:
                parsed.update(get_lcsc_info(parsed.get("pc")))
                all_data = load_data()
                all_data.append(parsed)
                save_data(all_data)
                qr_lidos.add(data_confirmado)
                print(f"✅ QR confirmado, salvo e enriquecido: {parsed}")
            del qr_nao_confirmados[data_confirmado]

    cap.release()
    cv2.destroyAllWindows()

# === ENVIO FINAL COM PROGRESSO ===
def send_all_parts():
    data = load_data()
    if not data: 
        print("⚠️ Nenhuma parte para enviar.")
        return
    total = len(data)
    for i, part in enumerate(data, 1):
        print(f"📤 Enviando parte {i}/{total} ({part.get('pc')})...", end="")
        if send_to_partsbox(part):
            print("✅")
        else:
            print("❌ Falha")
    print(f"✅ Envio concluído: {total} partes processadas.")
    save_data([])

# === MENU PRINCIPAL ===
def main():
    while True:
        choice = input("\n1 - Ler QR Code e salvar\n2 - Enviar todas as partes\n3 - Sair\nEscolha: ")
        if choice=="1": scan_qr()
        elif choice=="2": send_all_parts()
        elif choice=="3": break
        else: print("Opção inválida.")

if __name__ == "__main__":
    main()
