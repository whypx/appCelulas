from pathlib import Path

from .analises import GerenciadorAnalises
from .contador import ContadorCelulas


class SessaoCelular:
    def __init__(self, pasta_dados, pasta_cache):
        self.analises = GerenciadorAnalises(pasta_dados)
        self.cache = Path(pasta_cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.contador = None

    def carregar(self, caminho, nome):
        novo = ContadorCelulas(caminho)
        novo.nome = nome
        antigo = self.contador
        self.contador = novo
        if antigo is not None and antigo.caminho != novo.caminho and antigo.caminho.parent == self.cache:
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
        return self.contador.desenhar_marcadores()

    def marcar(self, x, y, distancia):
        return self.contador.marcar_na_previa(x, y, distancia)

    def desfazer(self):
        if self.contador.desfazer_marcacao():
            return "Última marcação removida."
        return "Nenhuma marcação para desfazer."

    def limpar(self):
        self.contador.limpar_marcacoes()
        return "Marcações limpas."

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
        return linhas

    def consultar(self, identificador):
        registro = self.analises.carregar_analise(identificador)
        detalhes, previa = self.analises.rever_analise(registro)
        return {
            "titulo": registro["amostra"], "detalhes": detalhes,
            "previa": previa,
        }

    def resultados(self):
        registros = self.analises.listar_analises()
        total_salvo = 0
        for registro in registros:
            total_salvo += registro["total"]
        return self.total(), len(registros), total_salvo

    def exportar(self, tipo, destino):
        if tipo == "png":
            self.contador.desenhar_marcadores(resolucao_original=True).save(destino)
        else:
            self.analises.exportar_csv(Path(destino))
