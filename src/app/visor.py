import sys
from math import hypot

from toga import Canvas, Image


LIMITE_ARRASTE = 7


class VisorImagem(Canvas):
    def __init__(self, marcar, **estilo):
        self.marcar = marcar
        self.foto = None
        self.largura = 0
        self.altura = 0
        self.quadro = (0, 0, 0, 0)
        self.zoom = 1
        self.inicio = None
        self.ultimo = None
        self.moveu = False
        super().__init__(
            on_resize=self.redimensionar, on_press=self.pressionar,
            on_drag=self.arrastar, on_release=self.soltar, **estilo,
        )
        if sys.platform == "android":
            self.ouvinte = GestosAndroid(self)
            self._impl.native.setOnTouchListener(self.ouvinte)

    def exibir(self, previa, ajustar=False):
        foto = Image(previa)
        mudou = self.foto is None or foto.size != self.foto.size
        self.foto = foto
        if ajustar or mudou:
            self.ajustar()
        else:
            self.desenhar()

    def redimensionar(self, widget, width, height, **kwargs):
        if (width, height) != (self.largura, self.altura):
            self.largura, self.altura = width, height
            self.ajustar()

    def ajustar(self, widget=None):
        self.zoom = 1
        if self.foto is not None and self.largura and self.altura:
            escala = min(self.largura / self.foto.width, self.altura / self.foto.height)
            self.enquadrar(0, 0, self.foto.width * escala, self.foto.height * escala)

    def enquadrar(self, x, y, largura, altura):
        if largura <= self.largura:
            x = (self.largura - largura) / 2
        else:
            x = max(self.largura - largura, min(0, x))
        if altura <= self.altura:
            y = (self.altura - altura) / 2
        else:
            y = max(self.altura - altura, min(0, y))
        self.quadro = (x, y, largura, altura)
        self.desenhar()

    def desenhar(self):
        self.root_state.drawing_actions.clear()
        self.draw_image(self.foto, *self.quadro)

    def ampliar(self, widget=None):
        self.aplicar_zoom(2, self.largura / 2, self.altura / 2)

    def aplicar_zoom(self, fator, foco_x, foco_y, dx=0, dy=0):
        if self.foto is None:
            return
        novo_zoom = max(1, min(8, self.zoom * fator))
        escala = novo_zoom / self.zoom
        x, y, largura, altura = self.quadro
        self.zoom = novo_zoom
        self.enquadrar(
            foco_x + (x - foco_x) * escala + dx,
            foco_y + (y - foco_y) * escala + dy,
            largura * escala, altura * escala,
        )

    def pressionar(self, widget, x, y, **kwargs):
        self.inicio = (x, y)
        self.ultimo = (x, y)
        self.moveu = False

    def arrastar(self, widget, x, y, **kwargs):
        if self.inicio is None:
            return
        inicio_x, inicio_y = self.inicio
        if hypot(x - inicio_x, y - inicio_y) > LIMITE_ARRASTE:
            self.moveu = True
        if self.moveu and self.zoom > 1:
            esquerda, topo, largura, altura = self.quadro
            ultimo_x, ultimo_y = self.ultimo
            self.enquadrar(esquerda + x - ultimo_x, topo + y - ultimo_y, largura, altura)
            self.ultimo = (x, y)

    def soltar(self, widget, x, y, **kwargs):
        inicio = self.inicio
        self.inicio = None
        if self.foto is None or inicio is None or self.moveu:
            return
        inicio_x, inicio_y = inicio
        if hypot(x - inicio_x, y - inicio_y) > LIMITE_ARRASTE:
            return
        esquerda, topo, largura, altura = self.quadro
        if esquerda <= x < esquerda + largura and topo <= y < topo + altura:
            px = min(self.foto.width - 1, int((x - esquerda) * self.foto.width / largura))
            py = min(self.foto.height - 1, int((y - topo) * self.foto.height / altura))
            self.marcar(px, py)


if sys.platform == "android":
    from android.view import MotionEvent, View
    from java import dynamic_proxy

    class GestosAndroid(dynamic_proxy(View.OnTouchListener)):
        def __init__(self, visor):
            super().__init__()
            self.visor = visor
            self.pinca = None
            self.multitoque = False

        def onTouch(self, vista, evento):
            visor = self.visor
            if visor.foto is None:
                return False
            acao = evento.getActionMasked()
            densidade = visor._impl.dpi_scale
            x, y = evento.getX() / densidade, evento.getY() / densidade
            if acao == MotionEvent.ACTION_DOWN:
                self.multitoque = False
                visor.pressionar(visor, x, y)
            if acao == MotionEvent.ACTION_POINTER_DOWN:
                self.multitoque = True
                self.pinca = None
                visor.inicio = None
            if visor.zoom > 1 or self.multitoque:
                vista.getParent().requestDisallowInterceptTouchEvent(True)
            if acao == MotionEvent.ACTION_MOVE:
                if evento.getPointerCount() >= 2:
                    x2, y2 = evento.getX(1) / densidade, evento.getY(1) / densidade
                    distancia = hypot(x2 - x, y2 - y)
                    centro_x, centro_y = (x + x2) / 2, (y + y2) / 2
                    if self.pinca is not None and distancia > 0:
                        anterior, ax, ay = self.pinca
                        visor.aplicar_zoom(distancia / anterior, ax, ay, centro_x - ax, centro_y - ay)
                    if distancia > 0:
                        self.pinca = (distancia, centro_x, centro_y)
                elif not self.multitoque:
                    visor.arrastar(visor, x, y)
            if acao == MotionEvent.ACTION_POINTER_UP:
                self.pinca = None
            if acao == MotionEvent.ACTION_UP and not self.multitoque:
                visor.soltar(visor, x, y)
                vista.performClick()
            if acao in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                visor.inicio = None
                self.pinca = None
            return True
