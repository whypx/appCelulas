from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps


class ContadorCelulas:
    FORMATOS = {  # noqa: RUF012
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
        ".tif": "TIFF", ".tiff": "TIFF",
    }
    LIMITE_PREVIA = 1400
    RAIO_MARCADOR = 5
    COR_MARCADOR = "#46f6ff"
    COR_CONTORNO = "#082436"
    COR_SUGESTAO = "#3f1ac5"

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.nome = self.caminho.name
        self.extensao = self.caminho.suffix.lower()
        self.marcacoes = []
        self.sugestoes = []

        imagem = self.abrir_imagem()
        self.largura, self.altura = imagem.size
        imagem.thumbnail((self.LIMITE_PREVIA, self.LIMITE_PREVIA))
        self.previa = imagem

    def abrir_imagem(self):
        with Image.open(self.caminho) as imagem:
            formato_esperado = self.FORMATOS.get(self.extensao)
            if formato_esperado is None or imagem.format != formato_esperado:
                raise ValueError("O conteúdo da imagem não corresponde à extensão do arquivo.")
            imagem = ImageOps.exif_transpose(imagem)

        if imagem.mode.startswith("I") or imagem.mode == "F":
            imagem = imagem.convert("F")
            menor, maior = imagem.getextrema()
            if menor < maior and float("-inf") < menor and maior < float("inf"):
                escala = 255 / (maior - menor)

                def ajustar_tom(pixel):
                    return pixel * escala + (-menor * escala)

                imagem = imagem.point(ajustar_tom)
            imagem = imagem.convert("L")

        if "A" in imagem.getbands() or "transparency" in imagem.info:
            return imagem.convert("RGBA")
        return imagem.convert("RGB")

    def coordenadas_originais(self, x, y):
        if not (0 <= x < self.previa.width and 0 <= y < self.previa.height):
            raise ValueError("Clique dentro da imagem para marcar uma célula.")

        x_original = int((x + 0.5) * self.largura / self.previa.width)
        y_original = int((y + 0.5) * self.altura / self.previa.height)
        return x_original, y_original

    def adicionar_celula(self, x, y, distancia_minima):
        if distancia_minima > 0:
            for x_anterior, y_anterior in self.marcacoes:
                dx = x - x_anterior
                dy = y - y_anterior
                if dx ** 2 + dy ** 2 < distancia_minima ** 2:
                    return False

        self.marcacoes.append((x, y))
        return True

    def revisar_clique(self, x_previa, y_previa, distancia_minima):
        x, y = self.coordenadas_originais(x_previa, y_previa)
        if self.descartar_sugestao(x_previa, y_previa):
            restantes = len(self.sugestoes)
            return True, f"Sugestão rejeitada. Restam {restantes} para revisar."
        if self.adicionar_celula(x, y, distancia_minima):
            return True, f"Célula marcada em ({x}, {y})."
        return False, "Marcação muito próxima. Ajuste a distância mínima se forem células diferentes."

    def desfazer_marcacao(self):
        if self.marcacoes:
            self.marcacoes.pop()
            return True
        return False

    def limpar_marcacoes(self):
        self.marcacoes.clear()
        self.sugestoes.clear()

    def obter_total(self):
        return len(self.marcacoes)

    def _criar_mascara(self, limiar, claras):
        tons = self.previa.convert("L")
        tabela = []
        for tom in range(256):
            if claras:
                selecionado = tom >= limiar
            else:
                selecionado = tom <= limiar
            if selecionado:
                tabela.append(255)
            else:
                tabela.append(0)

        mascara = tons.point(tabela)
        if self.previa.mode == "RGBA":
            mascara = ImageChops.multiply(mascara, self.previa.getchannel("A"))
        return mascara

    def _medir_regiao(self, pixels, inicio, largura, altura):
        pilha = [inicio]
        pixels[inicio] = 0
        area = 0
        soma_x = 0
        soma_y = 0
        esquerda, topo, direita, base = largura, altura, 0, 0

        while pilha:
            y, x = divmod(pilha.pop(), largura)
            area += 1
            soma_x += x
            soma_y += y
            esquerda = min(esquerda, x)
            topo = min(topo, y)
            direita = max(direita, x)
            base = max(base, y)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                x_vizinho, y_vizinho = x + dx, y + dy
                if 0 <= x_vizinho < largura and 0 <= y_vizinho < altura:
                    vizinho = y_vizinho * largura + x_vizinho
                    if pixels[vizinho]:
                        pixels[vizinho] = 0
                        pilha.append(vizinho)

        centro = (soma_x / area, soma_y / area)
        caixa = (esquerda, topo, direita, base)
        return area, centro, caixa

    def detectar_celulas(self, limiar, claras, area_minima, area_maxima):
        mascara = self._criar_mascara(limiar, claras)

        self.sugestoes.clear()
        menor, maior = mascara.getextrema()
        if maior == 0 or menor > 0:
            return 0

        largura, altura = mascara.size
        fator_area = (self.largura / largura) * (self.altura / altura)
        pixels = bytearray(mascara.tobytes())
        for inicio, ativo in enumerate(pixels):
            if ativo == 0:
                continue
            area, centro, caixa = self._medir_regiao(pixels, inicio, largura, altura)
            esquerda, topo, direita, base = caixa
            if esquerda == 0 or topo == 0 or direita == largura - 1 or base == altura - 1:
                continue
            area_original = area * fator_area
            if area_original < area_minima:
                continue
            if area_maxima > 0 and area_original > area_maxima:
                continue
            x_centro, y_centro = centro
            ponto = self.coordenadas_originais(x_centro, y_centro)
            self.sugestoes.append((ponto, caixa))

        return len(self.sugestoes)

    def descartar_sugestao(self, x, y):
        for indice, (_, caixa) in enumerate(self.sugestoes):
            esquerda, topo, direita, base = caixa
            if esquerda <= x <= direita and topo <= y <= base:
                self.sugestoes.pop(indice)
                return True
        return False

    def incorporar_sugestoes(self, distancia_minima):
        adicionadas = 0
        for (x, y), _ in self.sugestoes:
            if self.adicionar_celula(x, y, distancia_minima):
                adicionadas += 1
        self.sugestoes.clear()
        return adicionadas

    def desenhar_marcadores(self, resolucao_original=False, mostrar_sugestoes=False):
        if resolucao_original:
            imagem = self.abrir_imagem()
            proporcao = max(self.largura / self.previa.width, self.altura / self.previa.height)
        else:
            imagem = self.previa.copy()
            proporcao = 1

        raio = round(self.RAIO_MARCADOR * proporcao)
        borda = max(1, round(proporcao))
        desenho = ImageDraw.Draw(imagem)

        if mostrar_sugestoes and not resolucao_original:
            for _, caixa in self.sugestoes:
                desenho.rectangle(caixa, outline=self.COR_SUGESTAO, width=2)

        for x, y in self.marcacoes:
            cx = int((x + 0.5) * imagem.width / self.largura)
            cy = int((y + 0.5) * imagem.height / self.altura)
            desenho.ellipse(
                (cx - raio, cy - raio, cx + raio, cy + raio),
                outline=self.COR_CONTORNO, width=2 * borda,
            )
            desenho.ellipse(
                (cx - raio + borda, cy - raio + borda,
                 cx + raio - borda, cy + raio - borda),
                outline=self.COR_MARCADOR, width=borda,
            )
        return imagem
