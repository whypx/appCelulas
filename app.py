import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import gradio as gr

from analises import GerenciadorAnalises
from contador import ContadorCelulas, ERROS_IMAGEM


SEM_IMAGEM = "Carregue uma imagem para começar a análise."
CSS = """
#marca { padding: 14px 22px; border-radius: 16px; color: #fff;
  background: linear-gradient(110deg, #112540, #214b78); }
#marca h1 { color: #fff; margin: 0; font-size: 30px; }
#marca p { color: #dceafb; margin: 4px 0; }
.painel { padding: 14px; border: 1px solid var(--border-color-primary);
  border-radius: 14px; background: var(--block-background-fill); }
#imagem { background: var(--background-fill-secondary); border-radius: 12px; }
#imagem img { cursor: crosshair; }
.medidas { display: flex; flex-wrap: wrap; gap: 12px; }
.medida { flex: 1 1 160px; padding: 12px 16px; border-radius: 12px;
  border: 1px solid var(--border-color-primary); background: var(--background-fill-secondary); }
.medida strong { display: block; font-size: 36px; line-height: 1.2; }
#total .medida { background: #2053a7; border-color: #2053a7; }
#total .medida span, #total .medida strong { color: #fff; }
"""


class AplicacaoCellCount:
    def __init__(self, pasta_dados=None):
        if pasta_dados is None:
            pasta_dados = Path(__file__).resolve().parent / "dados"
        self.analises = GerenciadorAnalises(pasta_dados)
        self.exportacoes = TemporaryDirectory(prefix="cellcount-")
        self.interface = self.construir_interface()

    def medida(self, rotulo, total):
        return f'<div class="medida" aria-live="polite"><span>{rotulo}</span><strong>{total}</strong></div>'

    def construir_interface(self):
        with gr.Blocks(title="CellCount", analytics_enabled=False) as tela:
            estado = gr.State()
            gr.HTML(
                "<h1>CellCount</h1><p>Sistema de Contagem e Análise Celular · PIBIC-EM / UFRN</p>",
                elem_id="marca",
            )
            with gr.Tab("Contagem"), gr.Row():
                with gr.Column(scale=3, min_width=330, elem_classes="painel"):
                    arquivo = gr.File(
                        label="Carregar imagem",
                        file_types=list(ContadorCelulas.FORMATOS), height=128, elem_id="carregamento",
                    )
                    info = gr.Textbox(label="Arquivo e resolução", placeholder="PNG, JPEG ou TIFF", interactive=False)
                    foto = gr.Image(format="png", interactive=False, show_label=False,
                                    height="clamp(300px, 47vh, 520px)", buttons=["fullscreen"], elem_id="imagem",
                                    alt_text="Imagem microscópica para marcar células")
                    with gr.Row():
                        desfazer = gr.Button("Desfazer")
                        limpar = gr.Button("Limpar marcações")
                with gr.Column(scale=2, min_width=280, elem_classes="painel"):
                    total = gr.HTML(self.medida("Células marcadas", 0), elem_id="total")
                    status = gr.Textbox(SEM_IMAGEM, label="Estado da análise", interactive=False)
                    amostra = gr.Textbox(label="Nome da amostra")
                    notas = gr.Textbox(label="Observações", lines=2)
                    distancia = gr.Slider(0, 100, 8, step=1, label="Distância mínima (px)", info="0 desliga a proteção.")
                    with gr.Accordion("Detecção assistida", open=False):
                        gr.Markdown("Clique dentro de uma caixa para rejeitá-la e fora dela para marcar.")
                        claras = gr.Checkbox(label="Células claras sobre fundo escuro")
                        limiar = gr.Slider(0, 255, 128, step=1, label="Limiar de brilho")
                        with gr.Row():
                            minima = gr.Number(25, precision=0, label="Área mínima (px²)")
                            maxima = gr.Number(0, precision=0, label="Área máxima (0 = livre)")
                        detectar = gr.Button("Detectar possíveis células")
                        with gr.Row():
                            incorporar = gr.Button("Incorporar sugestões")
                            descartar = gr.Button("Descartar todas")
                    salvar = gr.Button("Salvar análise", variant="primary")
                    gerar_png = gr.Button("Exportar imagem (PNG)")
                    png = gr.DownloadButton("Baixar PNG", visible=False)
            with gr.Tab("Histórico") as aba_historico:
                with gr.Column(elem_classes="painel"):
                    gr.Markdown("Selecione uma linha da tabela para rever a análise.")
                    tabela = gr.Dataframe(
                        headers=["Amostra", "Imagem", "Células", "Data e hora", "Identificador"],
                        datatype=["str", "str", "number", "str", "str"], value=[], interactive=False, buttons=[],
                    )
                    with gr.Row():
                        gerar_csv = gr.Button("Exportar resultados (CSV)", variant="primary")
                        csv = gr.DownloadButton("Baixar CSV", visible=False)
                with gr.Row():
                    with gr.Column(elem_classes="painel"):
                        detalhes = gr.Textbox(label="Registro selecionado", lines=7, interactive=False)
                        with gr.Accordion("Coordenadas em pixels (X, Y)", open=False):
                            pontos = gr.Dataframe(headers=["X", "Y"], datatype="number", value=[],
                                                  interactive=False, buttons=[])
                    foto_historico = gr.Image(label="Imagem da análise", format="png", height=360,
                                              interactive=False, buttons=["fullscreen"])
            with gr.Tab("Resultados") as aba_resultados:
                resultados = gr.HTML()

            fila = {"concurrency_id": "contagem", "concurrency_limit": 1, "api_visibility": "private"}
            saidas = [estado, foto, total, status, png]
            arquivo.change(self.carregar_imagem, arquivo, saidas + [info, amostra, notas], **fila)
            foto.select(self.marcar, [estado, distancia], saidas, trigger_mode="multiple", show_progress="hidden", **fila)
            desfazer.click(self.desfazer, estado, saidas, show_progress="hidden", **fila)
            limpar.click(self.limpar, estado, saidas, show_progress="hidden", **fila)
            detectar.click(self.detectar, [estado, limiar, claras, minima, maxima], saidas, **fila)
            incorporar.click(self.incorporar, [estado, distancia], saidas, **fila)
            descartar.click(self.descartar, estado, saidas, **fila)
            gravacao = salvar.click(self.salvar, [estado, amostra, notas], status, **fila)
            gerar_png.click(self.exportar_imagem, estado, [png, status], **fila)
            gr.on([tela.load, aba_historico.select, aba_resultados.select],
                  self.atualizar_historico, estado, [tabela, resultados], **fila)
            gravacao.success(self.atualizar_historico, estado, [tabela, resultados], **fila)
            tabela.select(self.consultar_analise, outputs=[detalhes, pontos, foto_historico], **fila)
            gerar_csv.click(self.exportar_csv, outputs=csv, **fila)
        return tela

    def atualizar_contagem(self, contador, mensagem):
        foto = None
        total = 0
        if contador is not None:
            foto = contador.desenhar_marcadores(mostrar_sugestoes=True)
            total = contador.obter_total()
        return contador, foto, self.medida("Células marcadas", total), mensagem, gr.update(value=None, visible=False)

    def exibir_mensagem(self, mensagem):
        return gr.skip(), gr.skip(), gr.skip(), mensagem, gr.skip()

    def carregar_imagem(self, caminho):
        contador, info, mensagem = None, "", SEM_IMAGEM
        if caminho:
            try:
                contador = ContadorCelulas(caminho)
            except ERROS_IMAGEM:
                mensagem = "Não foi possível abrir a imagem. Use PNG, JPEG ou TIFF compatível."
            else:
                info = f"{contador.nome} · {contador.largura} × {contador.altura} px"
                mensagem = "Clique sobre a imagem para marcar uma célula."
        return self.atualizar_contagem(contador, mensagem) + (info, "", "")

    def marcar(self, contador, distancia, evento: gr.SelectData):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        try:
            x, y = evento.index
            mudou, mensagem = contador.revisar_clique(x, y, distancia)
        except (TypeError, ValueError):
            return self.exibir_mensagem("Clique dentro da imagem.")
        if mudou:
            return self.atualizar_contagem(contador, mensagem)
        return self.exibir_mensagem(mensagem)

    def desfazer(self, contador):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        if contador.desfazer_marcacao():
            return self.atualizar_contagem(contador, "Última marcação removida.")
        return self.exibir_mensagem("Nenhuma marcação para desfazer.")

    def limpar(self, contador):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        contador.limpar_marcacoes()
        return self.atualizar_contagem(contador, "Marcações limpas.")

    def detectar(self, contador, limiar, claras, minima, maxima):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        if minima is None or maxima is None or minima < 1 or maxima < 0 or 0 < maxima < minima:
            return self.exibir_mensagem("A área mínima deve ser pelo menos 1. Use máxima de 0 ou igual ou superior à mínima.")
        quantidade = contador.detectar_celulas(limiar, claras, minima, maxima)
        return self.atualizar_contagem(contador, f"Sugestões para revisar · {quantidade}")

    def incorporar(self, contador, distancia):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        pendentes = len(contador.sugestoes)
        if not pendentes:
            return self.exibir_mensagem("Nenhuma sugestão para incorporar.")
        adicionadas = contador.incorporar_sugestoes(distancia)
        ignoradas = pendentes - adicionadas
        return self.atualizar_contagem(contador, f"Incorporadas · {adicionadas}. Ignoradas pela distância · {ignoradas}.")

    def descartar(self, contador):
        if contador is None:
            return self.exibir_mensagem(SEM_IMAGEM)
        contador.sugestoes.clear()
        return self.atualizar_contagem(contador, "Sugestões descartadas.")

    def salvar(self, contador, amostra, notas):
        if contador is None:
            raise gr.Error(SEM_IMAGEM)
        if not (amostra or "").strip():
            raise gr.Error("Informe o nome da amostra.")
        try:
            self.analises.salvar_analise(contador, amostra, notas or "")
        except OSError as erro:
            raise gr.Error("Não foi possível salvar a análise.") from erro
        return "Análise salva. Consulte a aba Histórico."

    def atualizar_historico(self, contador):
        linhas = []
        total_salvo = 0
        try:
            for registro in self.analises.listar_analises():
                data = self.analises.data_analise(registro).strftime("%d/%m/%Y %H:%M:%S %z")
                linhas.append([registro["amostra"], registro["imagem"], registro["total"], data, registro["id"]])
                total_salvo += registro["total"]
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível ler o histórico.") from erro
        atual = contador.obter_total() if contador is not None else 0
        resultados = (
            self.medida("Células da análise atual", atual)
            + self.medida("Análises registradas", len(linhas))
            + self.medida("Células nas análises salvas", total_salvo)
        )
        return linhas, f'<div class="medidas">{resultados}</div>'

    def consultar_analise(self, evento: gr.SelectData):
        linha = evento.row_value
        if not linha or len(linha) < 5 or not linha[4]:
            return gr.skip(), gr.skip(), gr.skip()
        try:
            registro = self.analises.carregar_analise(linha[4])
            detalhes, foto = self.analises.rever_analise(registro)
            return detalhes, registro["marcacoes"], foto
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível abrir o registro selecionado.") from erro

    def caminho_exportacao(self, nome):
        pasta = Path(self.exportacoes.name) / uuid4().hex
        pasta.mkdir()
        return pasta / nome

    def exportar_imagem(self, contador):
        if contador is None:
            return gr.update(value=None, visible=False), SEM_IMAGEM
        try:
            destino = self.caminho_exportacao("imagem-anotada.png")
            contador.desenhar_marcadores(resolucao_original=True).save(destino)
        except ERROS_IMAGEM as erro:
            raise gr.Error("Não foi possível exportar o PNG.") from erro
        return gr.update(value=str(destino), visible=True), "Imagem pronta para baixar."

    def exportar_csv(self):
        try:
            destino = self.caminho_exportacao("resultados-cellcount.csv")
            self.analises.exportar_csv(destino)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível exportar o CSV.") from erro
        return gr.update(value=str(destino), visible=True)

    def executar(self):
        colab = "COLAB_RELEASE_TAG" in os.environ or "google.colab" in sys.modules
        tema = gr.themes.Soft(primary_hue="blue", neutral_hue="slate", font=["Segoe UI", "system-ui"]).set(
            body_background_fill="#f1f5fa",
            body_background_fill_dark="#0d1726",
            button_primary_background_fill="#2053a7",
        )
        self.interface.launch(css=CSS, theme=tema, share=colab, debug=colab, footer_links=[])


if __name__ == "__main__":
    AplicacaoCellCount().executar()
