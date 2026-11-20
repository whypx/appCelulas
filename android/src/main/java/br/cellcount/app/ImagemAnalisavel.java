package br.cellcount.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;

final class ImagemAnalisavel extends View {
    interface Toque { void marcar(int x, int y); }

    private final Paint tinta = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final RectF quadro = new RectF();
    private final ScaleGestureDetector gestoZoom;
    private final GestureDetector gestoToque;
    private Bitmap imagem;
    private float zoom = 1;
    private boolean multitoque;

    ImagemAnalisavel(Context contexto, Toque toque) {
        super(contexto);
        setContentDescription("Prévia da imagem microscópica. Toque para marcar e amplie com dois dedos.");
        gestoZoom = new ScaleGestureDetector(contexto,
            new ScaleGestureDetector.SimpleOnScaleGestureListener() {
                @Override public boolean onScale(ScaleGestureDetector gesto) {
                    aplicarZoom(zoom * gesto.getScaleFactor(), gesto.getFocusX(), gesto.getFocusY());
                    return true;
                }
            });
        gestoZoom.setQuickScaleEnabled(false);
        gestoToque = new GestureDetector(contexto, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) { return true; }

            @Override public boolean onSingleTapUp(MotionEvent e) {
                if (!multitoque && quadro.contains(e.getX(), e.getY())) {
                    int x = (int) ((e.getX() - quadro.left) * imagem.getWidth() / quadro.width());
                    int y = (int) ((e.getY() - quadro.top) * imagem.getHeight() / quadro.height());
                    toque.marcar(x, y);
                    performClick();
                }
                return true;
            }

            @Override public boolean onScroll(MotionEvent a, MotionEvent b, float dx, float dy) {
                if (zoom > 1 && !multitoque) {
                    quadro.offset(-dx, -dy);
                    encaixar();
                    invalidate();
                }
                return zoom > 1;
            }
        });
    }

    void exibir(Bitmap nova, boolean reiniciar) {
        boolean mudouTamanho = imagem == null || nova == null ||
            imagem.getWidth() != nova.getWidth() || imagem.getHeight() != nova.getHeight();
        imagem = nova;
        if (reiniciar || mudouTamanho) ajustar();
        invalidate();
    }

    void ajustar() {
        zoom = 1;
        if (imagem == null || getWidth() == 0 || getHeight() == 0) {
            quadro.setEmpty();
        } else {
            float escala = Math.min((float) getWidth() / imagem.getWidth(),
                (float) getHeight() / imagem.getHeight());
            quadro.set(0, 0, imagem.getWidth() * escala, imagem.getHeight() * escala);
            encaixar();
        }
        invalidate();
    }

    void ampliar() { aplicarZoom(zoom * 2, getWidth() / 2f, getHeight() / 2f); }

    private void aplicarZoom(float novoZoom, float x, float y) {
        if (imagem == null || quadro.isEmpty()) return;
        novoZoom = Math.max(1, Math.min(8, novoZoom));
        float proporcao = novoZoom / zoom;
        quadro.set(x + (quadro.left - x) * proporcao, y + (quadro.top - y) * proporcao,
            x + (quadro.right - x) * proporcao, y + (quadro.bottom - y) * proporcao);
        zoom = novoZoom;
        encaixar();
        invalidate();
    }

    private void encaixar() {
        float largura = quadro.width();
        float altura = quadro.height();
        float x = largura <= getWidth() ? (getWidth() - largura) / 2
            : Math.max(getWidth() - largura, Math.min(0, quadro.left));
        float y = altura <= getHeight() ? (getHeight() - altura) / 2
            : Math.max(getHeight() - altura, Math.min(0, quadro.top));
        quadro.offsetTo(x, y);
    }

    @Override protected void onSizeChanged(int l, int a, int antesL, int antesA) { ajustar(); }

    @Override protected void onDraw(Canvas canvas) {
        if (imagem != null && !quadro.isEmpty()) canvas.drawBitmap(imagem, null, quadro, tinta);
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        if (imagem == null) return false;
        int acao = e.getActionMasked();
        if (acao == MotionEvent.ACTION_DOWN) multitoque = false;
        if (acao == MotionEvent.ACTION_POINTER_DOWN) multitoque = true;
        if (zoom > 1 || multitoque) getParent().requestDisallowInterceptTouchEvent(true);
        gestoZoom.onTouchEvent(e);
        gestoToque.onTouchEvent(e);
        return true;
    }

    @Override public boolean performClick() { return super.performClick(); }
}
