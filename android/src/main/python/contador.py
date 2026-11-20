from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ERROS_IMAGEM = (OSError, ValueError, Image.DecompressionBombError)


class ContadorCelulas:
    FORMATOS = {
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
        ".tif": "TIFF", ".tiff": "TIFF",
    }
    LIMITE_PREVIA = 1400
    RAIO_MARCADOR = 5
    COR_MARCADOR = "#46f6ff"
    COR_CONTORNO = "#082436"

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.nome = self.caminho.name
        self.extensao = self.caminho.suffix.lower()
        self.marcacoes = []

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

    def marcar_na_previa(self, x_previa, y_previa, distancia_minima):
        x, y = self.coordenadas_originais(x_previa, y_previa)
        if self.adicionar_celula(x, y, distancia_minima):
            return f"Célula marcada em ({x}, {y})."
        return "Marcação muito próxima. Ajuste a distância mínima se forem células diferentes."

    def desfazer_marcacao(self):
        if self.marcacoes:
            self.marcacoes.pop()
            return True
        return False

    def limpar_marcacoes(self):
        self.marcacoes.clear()

    def obter_total(self):
        return len(self.marcacoes)

    def desenhar_marcadores(self, resolucao_original=False):
        if resolucao_original:
            imagem = self.abrir_imagem()
            proporcao = max(self.largura / self.previa.width, self.altura / self.previa.height)
        else:
            imagem = self.previa.copy()
            proporcao = 1

        raio = round(self.RAIO_MARCADOR * proporcao)
        borda = max(1, round(proporcao))
        desenho = ImageDraw.Draw(imagem)

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
