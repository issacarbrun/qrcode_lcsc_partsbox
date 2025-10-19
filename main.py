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
PART_IDS_FILE = Path("part_ids.json")       # arquivo para salvar os ids

# === FUNÇÕES AUXILIARES ===
def parse_qr_data(qr_text):
    qr_text = qr_text.strip("{}[]")
    data = {}
    for item in qr_text.split(","):
        if ":" in item:
            k, v = item.split(":", 1)
            data[k.strip()] = v.strip().strip('"') or None
    return data if "pc" in data else None

def load_data(file_path=DATA_FILE):
    if not file_path.exists():
        file_path.write_text("[]", encoding="utf-8")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data, file_path=DATA_FILE):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# === SCRAPING LCSC ===
def get_lcsc_info(pc):
    url = f"https://www.lcsc.com/product-detail/{pc}.html?s_z=n_{pc}^"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return {}

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

    price_row = soup.select_one("table.priceTable tbody tr.major2--text")
    if price_row:
        try:
            price_text = price_row.select("td")[1].get_text(strip=True).replace("$", "").replace(",", "")
            info["unit_price"] = float(price_text)
        except:
            info["unit_price"] = None

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
        "part/tags": ["imported", "lcsc"],
        "part/cad-keys": [part.get("pc")]
    }
    resp = requests.post(f"{PARTSBOX_BASE_URL}/part/create", headers=headers, json=payload)
    if resp.status_code not in (200, 201):
        print(f"❌ Erro ao criar componente: {resp.status_code}")
        return None

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


# === ENVIO FINAL ===
def send_all_parts():
    data = load_data()
    if not data: 
        print("⚠️ Nenhuma parte para enviar.")
        return
    print(f"📤 Enviando {len(data)} partes para PartsBox...")
    success_count = 0
    for idx, part in enumerate(data, 1):
        part_id = send_to_partsbox(part)
        if part_id:
            print(f"[{idx}/{len(data)}] ✅ Parte enviada: {part.get('pc')} -> ID {part_id}")
            success_count += 1
        else:
            print(f"[{idx}/{len(data)}] ❌ Falha ao enviar: {part.get('pc')}")
    print(f"✅ Envio concluído: {success_count}/{len(data)} partes criadas com sucesso.")
    save_data([])

# === GERENCIAMENTO DE PARTSBOX ===
def get_all_part_ids():
    headers = {"Authorization": f"Token {PARTSBOX_API_KEY}"}
    response = requests.get(f"{PARTSBOX_BASE_URL}/part/all", headers=headers)
    if response.status_code != 200:
        print(f"❌ Erro ao buscar partes: {response.status_code}")
        return []
    data = response.json().get("data", [])
    part_ids = [part.get("part/id") for part in data if "part/id" in part]
    save_data(part_ids, PART_IDS_FILE)
    print(f"📋 Total de partes encontradas: {len(part_ids)} (salvo em {PART_IDS_FILE})")
    return part_ids

def delete_all_parts(confirm=False):
    if not confirm:
        print("⚠️ Para deletar todas as partes, passe confirm=True.")
        return
    part_ids = load_data(PART_IDS_FILE)
    if not part_ids:
        print("⚠️ Nenhuma parte encontrada para deletar.")
        return
    headers = {"Authorization": f"Token {PARTSBOX_API_KEY}"}
    for idx, part_id in enumerate(part_ids, 1):
        resp = requests.post(f"{PARTSBOX_BASE_URL}/part/delete", headers=headers, json={"part/id": part_id})
        status = resp.json().get("partsbox.status/category", "unknown")
        print(f"[{idx}/{len(part_ids)}] Parte {part_id}: {status}")
    print("✅ Exclusão de todas as partes processada.")
    save_data([], PART_IDS_FILE)

# === MENU PRINCIPAL ===
def main():
    while True:
        print("\n=== MENU ===")
        print("1 - Ler QR Code e salvar")
        print("2 - Enviar todas as partes")
        print("3 - Obter IDs de todas as partes e salvar")
        print("4 - Deletar todas as partes")
        print("5 - Sair")
        choice = input("Escolha uma opção: ")

        if choice == "1":
            scan_qr()
        elif choice == "2":
            send_all_parts()
        elif choice == "3":
            get_all_part_ids()
        elif choice == "4":
            confirm = input("Tem certeza que deseja deletar todas as partes? (sim/não): ").lower() == "sim"
            delete_all_parts(confirm=confirm)
        elif choice == "5":
            print("👋 Encerrando...")
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()
