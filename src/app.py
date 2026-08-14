import os
import sys
import uuid
from datetime import date

# Garante que o diretório de trabalho é a RAIZ do projeto (uma pasta acima
# de src/), não importa de onde o servidor (WSGI) inicia o processo.
# Todos os caminhos relativos do projeto ("modelos/", "imagens/uploads/",
# "recortes/", etc.) dependem disso para funcionar corretamente.
_PASTA_SRC = os.path.dirname(os.path.abspath(__file__))
_RAIZ_PROJETO = os.path.dirname(_PASTA_SRC)
os.chdir(_RAIZ_PROJETO)
sys.path.insert(0, _PASTA_SRC)

from flask import Flask, request, render_template, redirect, url_for, session

from core import processar_envio_foto, identificar_paciente_por_texto
from pacientes import buscar_paciente, cadastrar_paciente, listar_pacientes, definir_esquema_manutencao
from adesao import calcular_adesao, carregar_historico, hoje_brasil
from dosagem import listar_opcoes_manutencao

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento-trocar-em-producao")

# Senha simples compartilhada entre agentes -- trocar por login individual depois
SENHA_AGENTE = os.environ.get("SENHA_AGENTE", "trocar-esta-senha")


# ====================================
# PÁGINA PÚBLICA: paciente envia a foto
# ====================================
@app.route("/", methods=["GET"])
def pagina_envio():
    return render_template("enviar.html")


@app.route("/enviar", methods=["POST"])
def enviar_foto():
    identificacao = request.form.get("identificacao", "").strip()
    modelo_escolhido = request.form.get("modelo") or None
    arquivo = request.files.get("foto")

    if not identificacao or not arquivo:
        return render_template(
            "resultado.html",
            resultado={"sucesso": False, "mensagem": "Informe o SINAN ou nome completo e selecione uma foto."}
        )

    # Salva a foto num arquivo temporário com nome único -- pode ser
    # necessário preservá-la entre esta requisição e a de confirmação,
    # caso o nome informado seja ambíguo (mais de um paciente igual)
    token = uuid.uuid4().hex[:12]
    caminho_temp = os.path.join("temp_uploads", f"{token}.png")
    os.makedirs("temp_uploads", exist_ok=True)
    arquivo.save(caminho_temp)

    resultado_id = identificar_paciente_por_texto(identificacao)

    if resultado_id["candidatos"]:
        # Nome ambíguo -- mostra a lista para o paciente escolher, mantendo
        # a referência à foto já salva através do token
        return render_template(
            "selecionar_paciente.html",
            candidatos=resultado_id["candidatos"],
            token=token,
            modelo_escolhido=modelo_escolhido or "",
        )

    if resultado_id["paciente"] is None:
        return render_template(
            "resultado.html",
            resultado={
                "sucesso": False,
                "mensagem": "Não encontramos esse SINAN ou nome cadastrado. "
                            "Procure o agente de saúde para verificar o cadastro.",
            }
        )

    resultado = processar_envio_foto(
        resultado_id["paciente"]["id"], caminho_temp, modelo_forcado=modelo_escolhido
    )
    return render_template("resultado.html", resultado=resultado)


@app.route("/enviar/confirmar", methods=["POST"])
def confirmar_paciente_ambiguo():
    """
    Segunda etapa do fluxo de envio, usada só quando o nome informado
    bateu com mais de um paciente cadastrado -- o usuário escolhe qual é,
    e a foto (já salva com o token da etapa anterior) é processada agora.
    """
    paciente_id = request.form.get("paciente_id", "").strip()
    token = request.form.get("token", "").strip()
    modelo_escolhido = request.form.get("modelo_escolhido") or None

    caminho_temp = os.path.join("temp_uploads", f"{token}.png")
    if not os.path.exists(caminho_temp):
        return render_template(
            "resultado.html",
            resultado={"sucesso": False, "mensagem": "A foto expirou, envie novamente."}
        )

    resultado = processar_envio_foto(paciente_id, caminho_temp, modelo_forcado=modelo_escolhido)
    return render_template("resultado.html", resultado=resultado)


# ====================================
# ÁREA DO AGENTE (protegida por senha simples)
# ====================================
def agente_autenticado():
    return session.get("agente_ok", False)


@app.route("/agente/login", methods=["GET", "POST"])
def login_agente():
    erro = None
    if request.method == "POST":
        senha = request.form.get("senha", "")
        if senha == SENHA_AGENTE:
            session["agente_ok"] = True
            return redirect(url_for("painel"))
        erro = "Senha incorreta."
    return render_template("login.html", erro=erro)


@app.route("/agente/logout")
def logout_agente():
    session.pop("agente_ok", None)
    return redirect(url_for("login_agente"))


@app.route("/painel")
def painel():
    if not agente_autenticado():
        return redirect(url_for("login_agente"))

    pacientes = listar_pacientes()
    linhas = []
    for p in pacientes:
        try:
            relatorio = calcular_adesao(p["id"])
            pct_lista = [
                d["percentual_aderencia"] for d in relatorio["por_modelo"].values()
                if d["percentual_aderencia"] is not None
            ]
            pct_medio = round(sum(pct_lista) / len(pct_lista), 1) if pct_lista else None
            fase = relatorio["fase_atual"]
        except Exception:
            pct_medio = None
            fase = "desconhecida"

        linhas.append({
            "id": p["id"],
            "nome": p["nome"],
            "peso": p["peso"],
            "fase": fase,
            "aderencia": pct_medio,
        })

    return render_template("painel.html", pacientes=linhas)


@app.route("/agente/paciente/<sinan>")
def detalhe_paciente(sinan):
    if not agente_autenticado():
        return redirect(url_for("login_agente"))

    paciente = buscar_paciente(sinan)
    if paciente is None:
        return "Paciente não encontrado", 404

    relatorio = calcular_adesao(sinan)
    historico = carregar_historico(sinan)

    # Extrai os meses (YYYY-MM) que realmente têm leitura registrada,
    # para popular o seletor de relatório (mais recente primeiro)
    meses_disponiveis = sorted(
        {entrada["data"][:7] for entrada in historico}, reverse=True
    )

    return render_template(
        "paciente.html", paciente=paciente, relatorio=relatorio,
        historico=historico, meses_disponiveis=meses_disponiveis
    )


@app.route("/agente/cadastro", methods=["GET", "POST"])
def cadastro():
    if not agente_autenticado():
        return redirect(url_for("login_agente"))

    erro = None
    opcoes_manutencao = None

    if request.method == "POST":
        sinan = request.form.get("sinan", "").strip()
        nome = request.form.get("nome", "").strip()
        peso = request.form.get("peso", "").strip()
        data_inicio = request.form.get("data_inicio", "").strip() or str(hoje_brasil())
        esquema_indice = request.form.get("esquema_indice")

        try:
            peso_float = float(peso)
        except ValueError:
            return render_template("cadastro.html", erro="Peso inválido.")

        if buscar_paciente(sinan) is not None:
            return render_template("cadastro.html", erro="SINAN já cadastrado.")

        esquema = None
        if esquema_indice not in (None, ""):
            opcoes = listar_opcoes_manutencao(peso_float)
            esquema = opcoes[int(esquema_indice)]

        cadastrar_paciente(sinan, nome, peso_float, data_inicio, esquema_manutencao=esquema)
        return redirect(url_for("painel"))

    return render_template("cadastro.html", erro=erro)


@app.route("/agente/opcoes_manutencao")
def opcoes_manutencao_ajax():
    """Endpoint simples usado pelo formulário de cadastro para mostrar
    as opções válidas de esquema de manutenção conforme o peso digitado."""
    peso = request.args.get("peso", "")
    try:
        opcoes = listar_opcoes_manutencao(float(peso))
    except (ValueError, Exception):
        opcoes = []
    return {"opcoes": opcoes}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)