import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from contador import ContadorCelulas, ERROS_IMAGEM


class GerenciadorAnalises:
    CAMPOS_CSV = (
        "id", "amostra", "imagem", "largura", "altura", "total",
        "data_hora", "observacoes", "marcacoes",
    )
    TEXTOS_CSV = ("amostra", "imagem", "observacoes")

    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.pasta_imagens = self.pasta / "imagens"
        self.pasta_imagens.mkdir(parents=True, exist_ok=True)

    def salvar_analise(self, contador, amostra, observacoes):
        identificador = uuid4().hex
        arquivo_imagem = identificador + contador.extensao
        registro = {
            "id": identificador,
            "amostra": amostra.strip(),
            "imagem": contador.nome,
            "arquivo_imagem": arquivo_imagem,
            "largura": contador.largura,
            "altura": contador.altura,
            "total": contador.obter_total(),
            "data_hora": datetime.now().astimezone().isoformat(timespec="seconds"),
            "observacoes": observacoes.strip(),
            "marcacoes": contador.marcacoes.copy(),
        }

        imagem = self.pasta_imagens / arquivo_imagem
        temporario = self.pasta / f"{identificador}.tmp"
        destino = self.pasta / f"{identificador}.json"
        try:
            shutil.copyfile(contador.caminho, imagem)
            with temporario.open("w", encoding="utf-8") as arquivo:
                json.dump(registro, arquivo, ensure_ascii=False, indent=2)
            temporario.replace(destino)
        except OSError:
            temporario.unlink(missing_ok=True)
            imagem.unlink(missing_ok=True)
            raise
        return registro

    def listar_analises(self):
        registros = []
        for caminho in self.pasta.glob("*.json"):
            registros.append(self.carregar_analise(caminho.stem))
        return sorted(registros, key=self.data_analise, reverse=True)

    def carregar_analise(self, identificador):
        if not isinstance(identificador, str) or not identificador.isalnum():
            raise ValueError("Identificador de análise inválido.")
        caminho = self.pasta / f"{identificador}.json"
        with caminho.open(encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def data_analise(self, registro):
        return datetime.fromisoformat(registro["data_hora"])

    def caminho_imagem(self, registro):
        return self.pasta_imagens / Path(registro["arquivo_imagem"]).name

    def rever_analise(self, registro):
        data = self.data_analise(registro).strftime("%d/%m/%Y %H:%M:%S %z")
        detalhes = (
            f"Identificador: {registro['id']}\nAmostra: {registro['amostra']}\n"
            f"Imagem: {registro['imagem']} ({registro['largura']} × {registro['altura']} px)\n"
            f"Data e hora: {data}\nTotal de células: {registro['total']}\n"
            f"Observações: {registro['observacoes'] or 'Sem observações'}"
        )
        try:
            contador = ContadorCelulas(self.caminho_imagem(registro))
        except ERROS_IMAGEM:
            return detalhes + "\nImagem original indisponível.", None
        contador.marcacoes = registro["marcacoes"]
        return detalhes, contador.desenhar_marcadores()

    def texto_csv(self, texto):
        if texto.lstrip().startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r", "\n")):
            return "'" + texto
        return texto

    def exportar_csv(self, destino):
        registros = self.listar_analises()
        with destino.open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(self.CAMPOS_CSV)
            for registro in registros:
                linha = []
                for campo in self.CAMPOS_CSV:
                    valor = registro[campo]
                    if campo in self.TEXTOS_CSV:
                        valor = self.texto_csv(valor)
                    elif campo == "marcacoes":
                        valor = json.dumps(valor)
                    linha.append(valor)
                escritor.writerow(linha)
