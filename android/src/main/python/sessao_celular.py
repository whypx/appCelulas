import json
from pathlib import Path

from contador import ContadorCelulas
from analises import GerenciadorAnalises


class SessaoCelular:
    def __init__(self, pasta_dados, pasta_cache):
        self.analises = GerenciadorAnalises(pasta_dados)
        self.cache = Path(pasta_cache)
        self.contador = None

    def carregar(self, caminho, nome):
        novo = ContadorCelulas(caminho)
        novo.nome = nome
        antigo = self.contador
        self.contador = novo
        if antigo is not None:
            try:
                antigo.caminho.unlink(missing_ok=True)
            except OSError:
                pass
        return f"{novo.nome} · {novo.largura} × {novo.altura} px"

    def total(self):
        if self.contador is None:
            return 0
        return self.contador.obter_total()

    def previa(self):
        destino = self.cache / "previa-contagem.png"
        self.contador.desenhar_marcadores(mostrar_sugestoes=True).save(destino, compress_level=1)
        return str(destino)

    def marcar(self, x, y, distancia):
        _, mensagem = self.contador.revisar_clique(x, y, distancia)
        return mensagem

    def desfazer(self):
        if self.contador.desfazer_marcacao():
            return "Última marcação removida."
        return "Nenhuma marcação para desfazer."

    def limpar(self):
        self.contador.limpar_marcacoes()
        return "Marcações e sugestões limpas."

    def detectar(self, limiar, claras, area_minima, area_maxima):
        total = self.contador.detectar_celulas(limiar, claras, area_minima, area_maxima)
        if total == 0:
            return "Nenhuma sugestão. Ajuste o contraste, o limiar ou a área."
        return f"Sugestões para revisar · {total}"

    def incorporar(self, distancia):
        if not self.contador.sugestoes:
            return "Nenhuma sugestão para incorporar."
        candidatas = len(self.contador.sugestoes)
        adicionadas = self.contador.incorporar_sugestoes(distancia)
        ignoradas = candidatas - adicionadas
        return f"Pontos incorporados · {adicionadas}. Ignorados pela distância · {ignoradas}."

    def descartar(self):
        self.contador.sugestoes.clear()
        return "Sugestões descartadas."

    def salvar(self, amostra, observacoes):
        self.analises.salvar_analise(self.contador, amostra, observacoes)

    def historico(self):
        linhas = []
        for registro in self.analises.listar_analises():
            linhas.append({
                "id": registro["id"], "amostra": registro["amostra"],
                "imagem": registro["imagem"], "total": registro["total"],
                "data": self.analises.data_analise(registro).strftime("%d/%m/%Y %H:%M"),
            })
        return json.dumps(linhas, ensure_ascii=False)

    def consultar(self, identificador):
        registro = self.analises.carregar_analise(identificador)
        detalhes, imagem = self.analises.rever_analise(registro)
        previa = ""
        if imagem is not None:
            destino = self.cache / "previa-historico.png"
            imagem.save(destino, compress_level=1)
            previa = str(destino)
        pontos = []
        for x, y in registro["marcacoes"]:
            pontos.append(f"({x}, {y})")
        return json.dumps({
            "titulo": registro["amostra"], "detalhes": detalhes,
            "previa": previa, "pontos": "\n".join(pontos),
        }, ensure_ascii=False)

    def resultados(self):
        registros = self.analises.listar_analises()
        return json.dumps([self.total(), len(registros), sum(r["total"] for r in registros)])

    def exportar(self, tipo, destino):
        if tipo == "png":
            self.contador.desenhar_marcadores(resolucao_original=True).save(destino)
        else:
            self.analises.exportar_csv(Path(destino))
