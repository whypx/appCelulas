import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image

import gradio as gr
from analises import GerenciadorAnalises
from contador import ContadorCelulas

CSS = """
.gradio-container { background: var(--body-background-fill); }
#cabecalho {
    padding: 12px 22px;
    color: #fff;
    background: linear-gradient(112deg, #102239, #193b62);
    border-radius: 16px;
}
.marca { display: flex; align-items: center; gap: 15px; }
.marca h1 { margin: 0; color: #fff; font-size: 30px; line-height: 1.1; }
.marca p { margin: 5px 0 0; color: #dceafb; }
.marca .projeto { margin-left: auto; font-size: 13px; color: #bcd7f3; }
.simbolo {
    display: grid; place-items: center; flex: 0 0 48px; height: 48px;
    border-radius: 12px; background: #234e7c; color: #9de5ff;
    font-size: 30px; line-height: 1;
}
.painel {
    padding: 16px;
    gap: 10px;
    background: var(--block-background-fill);
    border: 1px solid var(--border-color-primary);
    border-radius: 14px;
}
.painel h2 { margin: 0; font-size: 19px; }
#visualizacao { background: var(--background-fill-secondary); border-radius: 12px; }
#visualizacao img { cursor: crosshair; }
.indicador {
    min-height: 106px;
    padding: 14px 18px;
    border: 1px solid var(--border-color-primary);
    border-radius: 12px;
    background: var(--background-fill-secondary);
    color: var(--body-text-color);
}
.indicador span { display: block; color: inherit; font-size: 14px; font-weight: 600; }
.indicador strong {
    display: block; color: inherit; font-size: 42px; line-height: 1.2;
    font-variant-numeric: tabular-nums;
}
#contagem-principal .indicador {
    color: #fff; background: #1c4ea0; border-color: #1c4ea0;
}
@media (max-width: 640px) {
    #cabecalho { padding: 16px; }
    .marca { flex-wrap: wrap; gap: 10px; }
    .marca .projeto { margin-left: 0; }
    .painel { padding: 12px; }
}
"""


class AplicacaoCellCount:
    """Conecta a interface ao contador da sessão e ao histórico em disco."""

    SEM_IMAGEM = "Carregue uma imagem para começar a análise."
    ERROS_IMAGEM = (OSError, ValueError, Image.DecompressionBombError)

    def __init__(self, pasta_dados=None):
        if pasta_dados is None:
            pasta_dados = Path(__file__).resolve().parent / "dados"
        self.analises = GerenciadorAnalises(pasta_dados)
        self.exportacoes = TemporaryDirectory(prefix="cellcount-")
        self.interface = self.construir_interface()

    def indicador(self, titulo, total):
        return (
            '<div class="indicador" aria-live="polite">'
            f"<span>{titulo}</span><strong>{total}</strong></div>"
        )

    def construir_interface(self):
        with gr.Blocks(title="CellCount", analytics_enabled=False) as interface:
            # Cada aba do navegador tem seu próprio objeto ContadorCelulas.
            estado = gr.State()
            gr.HTML(
                '<header class="marca">'
                '<span class="simbolo" aria-hidden="true">⊙</span>'
                "<div><h1>CellCount</h1><p>Sistema de Contagem e Análise Celular</p></div>"
                '<p class="projeto">PIBIC-EM / UFRN</p></header>',
                elem_id="cabecalho",
            )

            with gr.Tab("Contagem"):  # noqa: SIM117
                with gr.Row():
                    with gr.Column(scale=3, min_width=330, elem_classes="painel"):
                        gr.Markdown("## Imagem microscópica")
                        arquivo = gr.File(
                            label="Carregar imagem · PNG, JPG, JPEG ou TIFF",
                            file_types=list(ContadorCelulas.FORMATOS), type="filepath",
                            height=112, elem_id="carregamento",
                        )
                        info_imagem = gr.Textbox(
                            label="Arquivo e resolução", interactive=False, max_lines=1,
                        )
                        visualizacao = gr.Image(
                            type="pil", format="png", interactive=False, show_label=False,
                            height="clamp(320px, 44vh, 520px)", buttons=["fullscreen"],
                            elem_id="visualizacao",
                            alt_text="Imagem microscópica para contagem manual de células",
                        )
                        with gr.Row():
                            desfazer = gr.Button("Desfazer")
                            limpar = gr.Button("Limpar marcações")

                    with gr.Column(scale=2, min_width=280, elem_classes="painel"):
                        total = gr.HTML(self.indicador("Células marcadas", 0), elem_id="contagem-principal")
                        status = gr.Textbox(
                            value=self.SEM_IMAGEM, label="Estado da análise", interactive=False,
                        )
                        amostra = gr.Textbox(label="Nome da amostra", placeholder="Ex.: Amostra A")
                        observacoes = gr.Textbox(label="Observações", lines=4)
                        distancia = gr.Slider(
                            minimum=0, maximum=100, value=8, step=1, label="Distância mínima (px)",
                            info="Em pixels da imagem original. Use 0 para permitir pontos próximos ou iguais.",
                        )
                        salvar = gr.Button("Salvar análise", variant="primary")
                        exportar_png = gr.Button("Exportar imagem (PNG)")
                        baixar_png = gr.DownloadButton("Baixar PNG", visible=False)

            with gr.Tab("Histórico") as aba_historico:
                with gr.Column(elem_classes="painel"):
                    gr.Markdown("## Análises registradas")
                    resumo_historico = gr.Markdown("Nenhuma análise registrada.")
                    tabela = gr.Dataframe(
                        headers=["Amostra", "Imagem", "Células", "Data e hora", "Identificador"],
                        datatype=["str", "str", "number", "str", "str"], value=[],
                        interactive=False, show_label=False, buttons=[],
                    )
                    with gr.Row():
                        exportar_csv = gr.Button("Exportar resultados (CSV)", variant="primary")
                        baixar_csv = gr.DownloadButton("Baixar CSV", visible=False)
                with gr.Row():
                    with gr.Column(elem_classes="painel"):
                        gr.Markdown("## Dados da análise")
                        detalhes = gr.Textbox(
                            label="Registro selecionado", lines=7, interactive=False,
                            placeholder="Selecione uma linha da tabela.",
                        )
                        with gr.Accordion("Coordenadas em pixels (X, Y)", open=False):
                            coordenadas = gr.Dataframe(
                                headers=["X", "Y"], datatype="number", value=[],
                                interactive=False, show_label=False, buttons=[],
                            )
                    with gr.Column(elem_classes="painel"):
                        gr.Markdown("## Imagem da análise")
                        imagem_historico = gr.Image(
                            format="png", height=360, interactive=False, show_label=False,
                            buttons=["fullscreen"],
                        )

            with gr.Tab("Resultados") as aba_resultados:  # noqa: SIM117
                with gr.Row(elem_classes="painel"):
                    total_atual = gr.HTML(self.indicador("Células da análise atual", 0))
                    total_analises = gr.HTML(self.indicador("Análises registradas", 0))
                    total_celulas = gr.HTML(self.indicador("Células nas análises salvas", 0))

            # Os eventos de edição usam a mesma fila, para manter a ordem dos cliques.
            fila = {"concurrency_id": "contagem", "concurrency_limit": 1, "api_visibility": "private"}
            saidas_contagem = [estado, visualizacao, total, total_atual, status, baixar_png]
            arquivo.change(
                self.carregar_imagem, arquivo, saidas_contagem + [info_imagem, amostra, observacoes],
                **fila,
            )
            visualizacao.select(
                self.marcar_celula, [estado, distancia], saidas_contagem,
                trigger_mode="multiple", show_progress="hidden", **fila,
            )
            desfazer.click(self.desfazer, estado, saidas_contagem, show_progress="hidden", **fila)
            limpar.click(self.limpar, estado, saidas_contagem, show_progress="hidden", **fila)
            gravacao = salvar.click(self.salvar, [estado, amostra, observacoes], status, **fila)
            exportar_png.click(self.exportar_imagem, estado, [baixar_png, status], **fila)

            saidas_historico = [tabela, resumo_historico, total_analises, total_celulas]
            gr.on(
                [interface.load, aba_historico.select, aba_resultados.select],
                self.atualizar_historico, outputs=saidas_historico,
                show_progress="hidden", **fila,
            )
            gravacao.success(self.atualizar_historico, outputs=saidas_historico, **fila)
            tabela.select(
                self.consultar_analise, outputs=[detalhes, coordenadas, imagem_historico],
                api_visibility="private",
            )
            exportar_csv.click(self.exportar_resultados, outputs=baixar_csv, api_visibility="private")
        return interface

    def atualizacao_contagem(self, contador, mensagem):
        imagem = None
        total = 0
        if contador is not None:
            imagem = contador.desenhar_marcadores()
            total = contador.obter_total()
        return (
            contador, imagem, self.indicador("Células marcadas", total),
            self.indicador("Células da análise atual", total), mensagem,
            gr.update(value=None, visible=False),
        )

    def carregar_imagem(self, caminho):
        if caminho is None:
            return self.atualizacao_contagem(None, self.SEM_IMAGEM) + ("", "", "")
        try:
            contador = ContadorCelulas(caminho)
        except self.ERROS_IMAGEM:
            mensagem = "Não foi possível abrir a imagem. Verifique o arquivo e use PNG, JPEG ou TIFF compatível."
            return self.atualizacao_contagem(None, mensagem) + ("", "", "")

        info = f"{contador.nome} · {contador.largura} × {contador.altura} px"
        mensagem = "Clique sobre a imagem para marcar uma célula."
        return self.atualizacao_contagem(contador, mensagem) + (info, "", "")

    def sem_edicao(self, mensagem):
        return gr.skip(), gr.skip(), gr.skip(), gr.skip(), mensagem, gr.skip()

    def marcar_celula(self, contador, distancia, evento: gr.SelectData):
        if contador is None:
            return self.sem_edicao(self.SEM_IMAGEM)
        if not isinstance(evento.index, (list, tuple)) or len(evento.index) != 2:
            return self.sem_edicao("Clique dentro da imagem para marcar uma célula.")
        try:
            x, y = evento.index
            x, y = contador.coordenadas_originais(x, y)
        except (TypeError, ValueError):
            return self.sem_edicao("Clique dentro da imagem para marcar uma célula.")
        if not contador.adicionar_celula(x, y, distancia):
            return self.sem_edicao("Marcação muito próxima. Ajuste a distância mínima se forem células diferentes.")
        return self.atualizacao_contagem(contador, f"Célula marcada em ({x}, {y}).")

    def desfazer(self, contador):
        if contador is None:
            return self.sem_edicao(self.SEM_IMAGEM)
        if not contador.desfazer_marcacao():
            return self.sem_edicao("Nenhuma marcação para desfazer.")
        return self.atualizacao_contagem(contador, "Última marcação removida.")

    def limpar(self, contador):
        if contador is None:
            return self.sem_edicao(self.SEM_IMAGEM)
        contador.limpar_marcacoes()
        return self.atualizacao_contagem(contador, "Marcações limpas.")

    def salvar(self, contador, amostra, observacoes):
        if contador is None:
            raise gr.Error(self.SEM_IMAGEM)
        if not amostra.strip():
            raise gr.Error("Informe o nome da amostra antes de salvar.")
        try:
            self.analises.salvar_analise(contador, amostra, observacoes)
        except OSError as erro:
            raise gr.Error("Não foi possível salvar. Verifique a imagem e a pasta dados.") from erro
        return "Análise salva. O registro está disponível na aba Histórico."

    def atualizar_historico(self):
        try:
            registros = self.analises.listar_analises()
            linhas = []
            total_celulas = 0
            for registro in registros:
                data = self.analises.data_analise(registro).strftime("%d/%m/%Y %H:%M:%S %z")
                linhas.append([
                    registro["amostra"], registro["imagem"], registro["total"], data, registro["id"],
                ])
                total_celulas += registro["total"]
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível ler o histórico. Verifique os arquivos JSON da pasta dados.") from erro

        mensagem = "Nenhuma análise registrada."
        if linhas:
            mensagem = "Selecione uma linha para ver os dados e as marcações."
        return (
            linhas, mensagem, self.indicador("Análises registradas", len(linhas)),
            self.indicador("Células nas análises salvas", total_celulas),
        )

    def consultar_analise(self, evento: gr.SelectData):
        if not evento.row_value:
            return gr.skip(), gr.skip(), gr.skip()
        identificador = evento.row_value[4]
        try:
            registro = self.analises.carregar_analise(identificador)
            data = self.analises.data_analise(registro).strftime("%d/%m/%Y %H:%M:%S %z")
            detalhes = (
                f"Identificador: {registro['id']}\n"
                f"Amostra: {registro['amostra']}\n"
                f"Imagem: {registro['imagem']} ({registro['largura']} × {registro['altura']} px)\n"
                f"Data e hora: {data}\n"
                f"Total de células: {registro['total']}\n"
                f"Observações: {registro['observacoes'] or 'Sem observações'}"
            )
            pontos = registro["marcacoes"]
            caminho = self.analises.caminho_imagem(registro)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível abrir o registro selecionado.") from erro

        try:
            contador = ContadorCelulas(caminho)
            contador.marcacoes = pontos
            imagem = contador.desenhar_marcadores()
        except self.ERROS_IMAGEM:
            imagem = None
            detalhes += "\nImagem original indisponível. Os dados da análise foram preservados."
        return detalhes, pontos, imagem

    def caminho_exportacao(self, nome):
        # Uma pasta por exportação mantém os arquivos de sessões diferentes separados.
        pasta = Path(self.exportacoes.name) / uuid4().hex
        pasta.mkdir()
        return pasta / nome

    def exportar_imagem(self, contador):
        if contador is None:
            return gr.update(value=None, visible=False), self.SEM_IMAGEM
        try:
            destino = self.caminho_exportacao("imagem-anotada.png")
            contador.desenhar_marcadores(resolucao_original=True).save(destino)
        except self.ERROS_IMAGEM as erro:
            raise gr.Error("Não foi possível exportar o PNG. Verifique a imagem original.") from erro
        return gr.update(value=str(destino), visible=True), "Imagem anotada disponível para baixar."

    def exportar_resultados(self):
        try:
            destino = self.caminho_exportacao("resultados-cellcount.csv")
            self.analises.exportar_csv(destino)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise gr.Error("Não foi possível exportar o CSV. Verifique a pasta dados.") from erro
        return gr.update(value=str(destino), visible=True)

    def executar(self):
        # No Colab, o Gradio usa um link temporário para alcançar o servidor do notebook.
        no_colab = "COLAB_RELEASE_TAG" in os.environ or "google.colab" in sys.modules
        tema = gr.themes.Soft(
            primary_hue="blue", neutral_hue="slate", font=["Segoe UI", "system-ui", "sans-serif"],
        ).set(
            body_background_fill="#f2f6fb", body_background_fill_dark="#0d1726",
            block_label_background_fill="#e7effa", block_label_text_color="#234777",
            button_primary_background_fill="#2059b8",
            button_primary_background_fill_hover="#174695",
        )
        self.interface.launch(
            css=CSS, theme=tema, share=no_colab, debug=no_colab, footer_links=[],
        )


if __name__ == "__main__":
    AplicacaoCellCount().executar()
