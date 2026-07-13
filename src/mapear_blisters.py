import cv2
import json
import os
import numpy as np

MODELO = "rh_300_150"
IMAGEM = f"modelos/{MODELO}/referencia.png"
SAIDA_JSON = f"modelos/{MODELO}/blisters.json"

# Ajuste esses dois valores independentemente:
# RAIO_X = metade da LARGURA do comprimido, em pixels
# RAIO_Y = metade da ALTURA do comprimido, em pixels
# (meça no Paint/editor: largura e altura do domo separadamente)
RAIO_X = 74
RAIO_Y = 120   # aumente até a caixa cobrir topo/base do domo

ZOOM = 1.0

imagem = cv2.imread(IMAGEM)
if imagem is None:
    raise Exception(f"Não foi possível abrir {IMAGEM}")

h, w = imagem.shape[:2]
imagem_zoom = cv2.resize(imagem, (int(w * ZOOM), int(h * ZOOM)))

pontos = []
clone_zoom = imagem_zoom.copy()

def redesenhar():
    global clone_zoom
    clone_zoom = imagem_zoom.copy()
    for i, (x, y) in enumerate(pontos, start=1):
        xz, yz = int(x * ZOOM), int(y * ZOOM)
        rxz, ryz = int(RAIO_X * ZOOM), int(RAIO_Y * ZOOM)
        cv2.ellipse(clone_zoom, (xz, yz), (rxz, ryz), 0, 0, 360, (0, 255, 0), 2)
        cv2.circle(clone_zoom, (xz, yz), 3, (0, 0, 255), -1)
        cv2.putText(clone_zoom, f"P{i}", (xz - 10, yz - ryz - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.imshow("Mapear Blisters (clique=marcar, Z=desfazer, ENTER=salvar, ESC=sair)", clone_zoom)

def clique(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        x_orig = int(x / ZOOM)
        y_orig = int(y / ZOOM)
        pontos.append((x_orig, y_orig))
        redesenhar()

cv2.namedWindow("Mapear Blisters (clique=marcar, Z=desfazer, ENTER=salvar, ESC=sair)")
cv2.setMouseCallback("Mapear Blisters (clique=marcar, Z=desfazer, ENTER=salvar, ESC=sair)", clique)

print()
print("Clique no CENTRO de cada comprimido, na ordem P1, P2, P3...")
print("Z = desfaz o último ponto | ENTER = salva | ESC = cancela")
print()

redesenhar()

while True:
    tecla = cv2.waitKey(20) & 0xFF
    if tecla == 13:
        break
    elif tecla == 27:
        cv2.destroyAllWindows()
        exit()
    elif tecla in (ord('z'), ord('Z')):
        if pontos:
            pontos.pop()
            redesenhar()

cv2.destroyAllWindows()

# ====================================
# MONTA blisters.json (bounding box retangular a partir da elipse)
# ====================================

blisters = {}
for i, (x, y) in enumerate(pontos, start=1):
    x1 = max(0, x - RAIO_X)
    y1 = max(0, y - RAIO_Y)
    largura = RAIO_X * 2
    altura = RAIO_Y * 2
    blisters[f"P{i}"] = [x1, y1, largura, altura]

os.makedirs(os.path.dirname(SAIDA_JSON), exist_ok=True)
with open(SAIDA_JSON, "w", encoding="utf-8") as arquivo:
    json.dump(blisters, arquivo, indent=4)

print(f"\n{len(pontos)} cavidades salvas em {SAIDA_JSON}")