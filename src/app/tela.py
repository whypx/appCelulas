import sys
from asyncio import to_thread
from textwrap import fill

import toga

from .arquivos import Arquivos
from .sessao_celular import SessaoCelular
from .visor import VisorImagem


NOME_APP = "Contador de Células"
FUNDO = "#F2F6F5"
MARINHO = "#163538"
VERDE = "#10645B"
MENTA = "#DFEFEB"
ALERTA = "#96391F"
SUAVE = "#47636B"
BRANCO = "#FFFFFF"


class CellCount(toga.App):
    def startup(self):
        pasta = self.paths.data
        if sys.platform == "android":
            pasta = pasta.parent
            barra = self._impl.native.getSupportActionBar()
            if barra is not None:
                barra.hide()
        elif sys.platform == "win32":
            pasta = pasta.parent.with_name("CellCount") / pasta.name
        self.sessao = SessaoCelular(pasta / "dados", self.paths.cache)
        self.arquivos = Arquivos(self)
        self.ocupado = False
        self.main_window = toga.MainWindow(title=self.formal_name, size=(540, 820))
        self.contagem = self.montar_contagem()
        self.conteudo = toga.ScrollContainer(horizontal=False, flex=1, background_color=FUNDO)
        self.abas = [
            self.botao("Contagem", self.abrir_contagem),
            self.botao("Histórico", self.abrir_historico),
            self.botao("Resultados", self.abrir_resultados),
        ]
        menu = toga.Box(children=self.abas, direction="row", gap=7, margin=(8, 12))
        cabecalho = self.cartao(
            self.texto(NOME_APP, 23, BRANCO, forte=True),
            self.texto("Análise manual de imagens", 12, "#BDE6E0"),
            cor=MARINHO,
        )
        self.main_window.content = toga.Box(
            children=[cabecalho, menu, self.conteudo], direction="column", background_color=FUNDO,
        )
        self.abrir_contagem()
        self.main_window.show()

    def texto(self, valor, tamanho=14, cor=MARINHO, forte=False, **estilo):
        peso = "normal"
        if forte:
            peso = "bold"
        return toga.Label(valor, font_size=tamanho, color=cor, font_weight=peso, **estilo)

    def botao(self, titulo, acao, principal=False):
        texto, fundo = MARINHO, MENTA
        if principal:
            texto, fundo = BRANCO, VERDE
        return toga.Button(
            titulo, on_press=acao, flex=1, height=44,
            color=texto, background_color=fundo,
        )

    def linha(self, *itens):
        return toga.Box(children=itens, direction="row", gap=8)

    def cartao(self, *itens, cor=BRANCO):
        interior = toga.Box(children=itens, direction="column", margin=14, gap=8)
        return toga.Box(children=[interior], direction="column", background_color=cor)

    def pagina(self, *itens):
        return toga.Box(children=itens, direction="column", margin=(4, 12, 16), gap=12)

    def mostrar(self, pagina, aba):
        for indice, botao in enumerate(self.abas):
            if indice == aba:
                botao.style.background_color = VERDE
                botao.style.color = BRANCO
            else:
                botao.style.background_color = MENTA
                botao.style.color = MARINHO
        if self.conteudo.content is not pagina:
            self.conteudo.content = pagina
            self.conteudo.vertical_position = 0

    def montar_contagem(self):
        self.numero = self.texto("0", 32, BRANCO, forte=True)
        rotulo_total = self.texto("Células marcadas", 16, BRANCO, flex=1)
        total = self.cartao(self.linha(rotulo_total, self.numero), cor=MARINHO)
        self.arquivo = self.texto("Carregue uma imagem para começar\na análise. Use PNG, JPEG ou TIFF.", 13, SUAVE)
        self.estado = self.texto("", 13, SUAVE)
        self.visor = VisorImagem(self.marcar, height=260, background_color=MARINHO)
        self.distancia = toga.TextInput(value="8", width=55)
        rotulo_distancia = self.texto("Distância mínima (px)\n0 permite repetir o ponto", 12, SUAVE, flex=1)
        distancia = self.linha(rotulo_distancia, self.distancia)
        self.abrir = self.botao("Abrir imagem", self.abrir_imagem, principal=True)
        imagem = self.cartao(
            self.texto("Imagem da amostra", 19, forte=True),
            self.arquivo, self.linha(self.abrir),
        )
        self.ferramentas = self.cartao(
            self.visor, self.estado,
            self.linha(self.botao("Ampliar", self.visor.ampliar), self.botao("Ajustar", self.visor.ajustar)),
            self.linha(self.botao("Desfazer", self.desfazer), self.botao("Limpar", self.limpar)),
            distancia,
        )
        self.amostra = toga.TextInput()
        self.observacoes = toga.MultilineTextInput(height=75)
        self.aviso_nome = self.texto("Informe o nome da amostra.", 13, ALERTA, display="none")
        self.registro = self.cartao(
            self.texto("Registrar análise", 19, forte=True),
            self.texto("Nome da amostra", forte=True), self.amostra, self.aviso_nome,
            self.texto("Observações (opcional)"), self.observacoes,
            self.linha(self.botao("Salvar análise", self.salvar, principal=True),
                       self.botao("Exportar PNG", self.exportar_png)),
        )
        self.ferramentas.style.display = "none"
        self.registro.style.display = "none"
        return self.pagina(imagem, total, self.ferramentas, self.registro)

    def abrir_contagem(self, widget=None):
        if not self.ocupado:
            self.mostrar(self.contagem, 0)

    async def abrir_imagem(self, widget):
        if self.ocupado:
            return
        self.ocupado = True
        try:
            escolha = await self.arquivos.escolher(self.sessao.cache)
            if escolha is None:
                return
            copia, nome = escolha
            try:
                descricao = await to_thread(self.sessao.carregar, copia, nome)
            except Exception:
                copia.unlink(missing_ok=True)
                raise
            self.arquivo.text = fill(descricao, width=28)
            self.abrir.text = "Trocar imagem"
            self.abrir.style.background_color = MENTA
            self.abrir.style.color = MARINHO
            self.ferramentas.style.display = "pack"
            self.registro.style.display = "pack"
            self.aviso_nome.style.display = "none"
            self.amostra.value = ""
            self.observacoes.value = ""
            self.atualizar("Toque na célula para marcar.", ajustar=True)
        except ValueError as erro:
            await self.alerta("Não foi possível abrir a imagem", str(erro))
        except Exception:
            await self.alerta("Não foi possível abrir a imagem", "Escolha um PNG, JPEG ou TIFF compatível.")
        finally:
            self.ocupado = False

    def atualizar(self, mensagem, ajustar=False):
        self.visor.exibir(self.sessao.previa(), ajustar=ajustar)
        self.numero.text = str(self.sessao.total())
        self.estado.style.color = SUAVE
        self.estado.text = fill(mensagem, width=30)

    def marcar(self, x, y):
        if self.ocupado or self.sessao.contador is None:
            return
        try:
            limite = int(self.distancia.value)
            if not 0 <= limite <= 100:
                raise ValueError
        except ValueError:
            self.estado.style.color = ALERTA
            self.estado.text = "Use um inteiro entre 0 e 100 px."
            self.distancia.focus()
            return
        self.atualizar(self.sessao.marcar(x, y, limite))

    def desfazer(self, widget):
        if not self.ocupado:
            self.atualizar(self.sessao.desfazer())

    async def limpar(self, widget):
        if self.ocupado:
            return
        self.ocupado = True
        try:
            confirmar = await self.main_window.dialog(toga.ConfirmDialog(
                "Limpar marcações?", "Todos os pontos da contagem atual serão removidos.",
            ))
            if confirmar:
                self.atualizar(self.sessao.limpar())
        finally:
            self.ocupado = False

    async def salvar(self, widget):
        if self.ocupado:
            return
        nome = self.amostra.value.strip()
        if not nome:
            self.aviso_nome.style.display = "pack"
            self.amostra.focus()
            return
        self.ocupado = True
        try:
            self.aviso_nome.style.display = "none"
            await to_thread(self.sessao.salvar, nome, self.observacoes.value)
            self.estado.style.color = SUAVE
            self.estado.text = "Análise salva no histórico."
            await self.main_window.dialog(toga.InfoDialog("Análise salva", nome))
        except Exception:
            await self.alerta("Falha ao salvar", "Verifique se há espaço disponível e tente novamente.")
        finally:
            self.ocupado = False

    async def alerta(self, titulo, mensagem):
        await self.main_window.dialog(toga.ErrorDialog(titulo, mensagem))

    def abrir_historico(self, widget=None):
        if self.ocupado:
            return
        pagina = self.pagina(self.texto("Histórico", 23, forte=True))
        pagina.add(self.linha(self.botao("Exportar CSV", self.exportar_csv, principal=True)))
        try:
            registros = self.sessao.historico()
        except (OSError, ValueError, KeyError, TypeError):
            pagina.add(self.cartao(self.texto("Falha ao ler o histórico.")))
            registros = []
        else:
            if not registros:
                pagina.add(self.cartao(self.texto("Nenhuma análise salva.")))
        for registro in registros:
            detalhe = f"{registro['total']} células · {registro['data']}"
            abrir = self.botao("Ver análise", self.ver_analise)
            abrir.id_analise = registro["id"]
            pagina.add(self.cartao(
                self.texto(fill(registro["amostra"], 20), 17, forte=True),
                self.texto(detalhe, 13, SUAVE),
                self.texto(fill(registro["imagem"], 28), 13, SUAVE), self.linha(abrir),
            ))
        self.mostrar(pagina, 1)

    async def ver_analise(self, widget):
        if self.ocupado:
            return
        self.ocupado = True
        try:
            registro = await to_thread(self.sessao.consultar, widget.id_analise)
            apagar = self.botao("Apagar análise", self.apagar_analise)
            apagar.id_analise = widget.id_analise
            pagina = self.pagina(
                self.linha(self.botao("Voltar ao histórico", self.abrir_historico)),
                self.texto(fill(registro["titulo"], 16), 23, forte=True),
            )
            if registro["previa"] is not None:
                foto = toga.Image(registro["previa"])
                pagina.add(toga.ImageView(foto, height=250))
            pagina.add(self.cartao(toga.MultilineTextInput(
                value=registro["detalhes"], readonly=True, height=165,
            )))
            pagina.add(self.linha(apagar))
            self.mostrar(pagina, 1)
        except Exception:
            await self.alerta("Falha na consulta", "Não foi possível abrir esta análise.")
        finally:
            self.ocupado = False

    async def apagar_analise(self, widget):
        if self.ocupado:
            return
        self.ocupado = True
        try:
            confirmou = await self.main_window.dialog(toga.ConfirmDialog(
                "Apagar esta análise?", "A análise e a imagem guardada no histórico serão removidas.",
            ))
            if not confirmou:
                return
            await to_thread(self.sessao.analises.apagar_analise, widget.id_analise)
        except (OSError, ValueError, KeyError, TypeError):
            await self.alerta("Não foi possível apagar", "Confira o histórico e tente novamente.")
        finally:
            self.ocupado = False
        self.abrir_historico()

    def abrir_resultados(self, widget):
        if self.ocupado:
            return
        pagina = self.pagina(self.texto("Resultados", 23, forte=True))
        rotulos = ("Células na análise atual", "Análises salvas", "Células nas análises salvas")
        try:
            for rotulo, valor in zip(rotulos, self.sessao.resultados()):
                pagina.add(self.cartao(self.texto(rotulo, 14, SUAVE),
                                       self.texto(str(valor), 28, VERDE, forte=True)))
        except (OSError, ValueError, KeyError, TypeError):
            pagina.add(self.cartao(self.texto("Falha ao ler os resultados.")))
        self.mostrar(pagina, 2)

    async def exportar_png(self, widget):
        await self.exportar("png")

    async def exportar_csv(self, widget):
        await self.exportar("csv")

    async def exportar(self, tipo):
        if self.ocupado:
            return
        self.ocupado = True
        try:
            if await self.arquivos.exportar(self.sessao, tipo):
                await self.main_window.dialog(toga.InfoDialog("Exportação concluída", f"Arquivo {tipo.upper()} salvo."))
        except Exception:
            await self.alerta("Falha na exportação", "Escolha um destino com permissão de escrita.")
        finally:
            self.ocupado = False
