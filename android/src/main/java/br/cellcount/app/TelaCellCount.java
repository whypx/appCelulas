package br.cellcount.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.text.InputType;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.webkit.MimeTypeMap;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Locale;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class TelaCellCount extends Activity {
    private static final int ABRIR = 21, PNG = 22, CSV = 23;
    private static final int MARINHO = 0xff112540, AZUL = 0xff2456c5;
    private static final int FUNDO = 0xfff1f5fa, LINHA = 0xffdee7f2, CINZA = 0xff49607a;
    private static final String SEM_IMAGEM = "Carregue uma imagem para começar a análise.";

    private final ExecutorService fila = Executors.newSingleThreadExecutor();
    private final ScrollView[] telas = new ScrollView[3];
    private final Button[] abas = new Button[3];
    private PyObject sessao;
    private ImagemAnalisavel imagem;
    private TextView numero, estado, arquivo, vazio;
    private LinearLayout historico, resultados;
    private EditText amostra, observacoes, distancia, limiar, minima, maxima;
    private Switch claras;
    private boolean ocupado, temImagem;

    @Override protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        LinearLayout raiz = coluna();
        raiz.setBackgroundColor(FUNDO);
        raiz.setFocusableInTouchMode(true);
        LinearLayout cabecalho = coluna();
        margemInterna(cabecalho, 18, 12);
        cabecalho.setBackgroundColor(MARINHO);
        cabecalho.addView(texto("CellCount", 26, Color.WHITE, true));
        cabecalho.addView(texto("Contagem e análise celular · PIBIC-EM/UFRN", 13, 0xffcfdef5, false));
        raiz.addView(cabecalho);

        LinearLayout menu = linha();
        margemInterna(menu, 10, 6);
        String[] titulos = {"Contagem", "Histórico", "Resultados"};
        for (int i = 0; i < abas.length; i++) {
            int indice = i;
            abas[i] = botao(titulos[i], false, () -> abrirAba(indice));
            adicionarNaLinha(menu, abas[i]);
        }
        raiz.addView(menu);

        FrameLayout corpo = new FrameLayout(this);
        telas[0] = montarContagem();
        telas[1] = rolagem(historico = painelPagina());
        telas[2] = rolagem(resultados = painelPagina());
        for (ScrollView tela : telas) corpo.addView(tela);
        raiz.addView(corpo, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(raiz);
        raiz.requestFocus();
        abrirAba(0);
    }

    private ScrollView montarContagem() {
        LinearLayout conteudo = painelPagina();
        LinearLayout cartaoTotal = cartao();
        cartaoTotal.setBackground(fundo(AZUL, 16, AZUL));
        cartaoTotal.addView(texto("Células confirmadas", 14, Color.WHITE, true));
        numero = texto("0", 38, Color.WHITE, true);
        cartaoTotal.addView(numero);
        comEspaco(conteudo, cartaoTotal);

        LinearLayout cartaoImagem = cartao();
        comEspaco(cartaoImagem, botao("Abrir imagem", true, this::escolherImagem));
        arquivo = texto("PNG, JPEG ou TIFF", 13, CINZA, false);
        comEspaco(cartaoImagem, arquivo);
        FrameLayout visor = new FrameLayout(this);
        visor.setBackground(fundo(0xffe8eff8, 12, LINHA));
        visor.setClipToOutline(true);
        imagem = new ImagemAnalisavel(this, this::marcar);
        visor.addView(imagem, new FrameLayout.LayoutParams(-1, -1));
        vazio = texto("Adicione uma imagem microscópica", 14, CINZA, false);
        vazio.setGravity(Gravity.CENTER);
        visor.addView(vazio, new FrameLayout.LayoutParams(-1, -1));
        LinearLayout.LayoutParams alturaVisor = new LinearLayout.LayoutParams(-1, dp(280));
        alturaVisor.bottomMargin = dp(8);
        cartaoImagem.addView(visor, alturaVisor);
        estado = texto(SEM_IMAGEM, 14, CINZA, false);
        estado.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        comEspaco(cartaoImagem, estado);
        LinearLayout zoom = linha();
        adicionarNaLinha(zoom, botao("Ampliar", false, imagem::ampliar));
        adicionarNaLinha(zoom, botao("Ajustar", false, imagem::ajustar));
        comEspaco(cartaoImagem, zoom);
        LinearLayout edicao = linha();
        adicionarNaLinha(edicao, botao("Desfazer", false, () -> editar("desfazer")));
        adicionarNaLinha(edicao, botao("Limpar", false, this::confirmarLimpeza));
        comEspaco(cartaoImagem, edicao);
        comEspaco(conteudo, cartaoImagem);

        LinearLayout cartaoDeteccao = cartao();
        LinearLayout ajuste = coluna();
        ajuste.setVisibility(View.GONE);
        Button mostrar = botao("Detecção assistida ▾", false, () -> {
            boolean expandir = ajuste.getVisibility() != View.VISIBLE;
            ajuste.setVisibility(expandir ? View.VISIBLE : View.GONE);
        });
        comEspaco(cartaoDeteccao, mostrar);
        claras = new Switch(this);
        claras.setText("Células claras sobre fundo escuro");
        claras.setTextColor(MARINHO);
        comEspaco(ajuste, claras);
        limiar = campo(ajuste, "Limiar de brilho (0 a 255)", "128", InputType.TYPE_CLASS_NUMBER);
        LinearLayout areas = linha();
        LinearLayout esquerda = coluna(), direita = coluna();
        minima = campo(esquerda, "Área mínima (px²)", "25", InputType.TYPE_CLASS_NUMBER);
        maxima = campo(direita, "Área máxima (0 = livre)", "0", InputType.TYPE_CLASS_NUMBER);
        adicionarNaLinha(areas, esquerda);
        adicionarNaLinha(areas, direita);
        comEspaco(ajuste, areas);
        comEspaco(ajuste, texto("Toque numa caixa de sugestão para rejeitá-la e incorpore as restantes.",
            14, CINZA, false));
        comEspaco(ajuste, botao("Detectar possíveis células", true, this::detectar));
        comEspaco(ajuste, botao("Incorporar sugestões", false, () -> editarComDistancia("incorporar")));
        comEspaco(ajuste, botao("Descartar todas", false, () -> editar("descartar")));
        cartaoDeteccao.addView(ajuste);
        comEspaco(conteudo, cartaoDeteccao);

        LinearLayout registro = cartao();
        comEspaco(registro, texto("Registrar análise", 19, MARINHO, true));
        amostra = campo(registro, "Nome da amostra", "", InputType.TYPE_CLASS_TEXT);
        observacoes = campo(registro, "Observações", "", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        distancia = campo(registro, "Distância mínima (px, 0 = desligada)", "8", InputType.TYPE_CLASS_NUMBER);
        comEspaco(registro, botao("Salvar análise", true, this::salvar));
        comEspaco(registro, botao("Exportar imagem (PNG)", false, () -> escolherExportacao(PNG)));
        comEspaco(conteudo, registro);
        return rolagem(conteudo);
    }

    private void abrirAba(int indice) {
        if (ocupado) return;
        for (int i = 0; i < telas.length; i++) {
            telas[i].setVisibility(i == indice ? View.VISIBLE : View.GONE);
            pintarBotao(abas[i], i == indice);
            abas[i].setSelected(i == indice);
        }
        if (indice == 1) atualizarHistorico();
        if (indice == 2) atualizarResultados();
    }

    private PyObject sessao() {
        if (sessao == null) {
            File dados = new File(getFilesDir(), "dados");
            sessao = Python.getInstance().getModule("sessao_celular").callAttr("SessaoCelular",
                dados.getAbsolutePath(), getCacheDir().getAbsolutePath());
        }
        return sessao;
    }

    private void executar(String falha, Callable<Runnable> tarefa) {
        if (ocupado) return;
        ocupado = true;
        fila.execute(() -> {
            try {
                Runnable atualizar = tarefa.call();
                runOnUiThread(() -> {
                    ocupado = false;
                    if (!isDestroyed()) atualizar.run();
                });
            } catch (Exception erro) {
                Log.e("CellCount", falha, erro);
                runOnUiThread(() -> {
                    ocupado = false;
                    if (!isDestroyed()) avisar(falha);
                });
            }
        });
    }

    private void escolherImagem() {
        if (ocupado) return;
        Intent abrir = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        abrir.addCategory(Intent.CATEGORY_OPENABLE);
        abrir.setType("*/*");
        startActivityForResult(abrir, ABRIR);
    }

    @Override protected void onActivityResult(int pedido, int codigo, Intent resposta) {
        super.onActivityResult(pedido, codigo, resposta);
        if (codigo != RESULT_OK || resposta == null || resposta.getData() == null) return;
        Uri endereco = resposta.getData();
        if (pedido == ABRIR) carregar(endereco);
        if (pedido == PNG || pedido == CSV) gravarExportacao(endereco, pedido);
    }

    private String nomeOriginal(Uri endereco) {
        try (Cursor linha = getContentResolver().query(endereco,
                new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (linha != null && linha.moveToFirst() && !linha.isNull(0)) return linha.getString(0);
        }
        String extensao = MimeTypeMap.getSingleton().getExtensionFromMimeType(getContentResolver().getType(endereco));
        return extensao == null ? "imagem" : "imagem." + extensao;
    }

    private void carregar(Uri endereco) {
        estado.setText("Carregando imagem…");
        executar("Não foi possível abrir a imagem. Use PNG, JPEG ou TIFF compatível.", () -> {
            String nome = nomeOriginal(endereco);
            int ponto = nome.lastIndexOf('.');
            String extensao = ponto < 0 ? "" : nome.substring(ponto).toLowerCase(Locale.ROOT);
            if (!extensao.equals(".png") && !extensao.equals(".jpg") && !extensao.equals(".jpeg")
                    && !extensao.equals(".tif") && !extensao.equals(".tiff")) {
                throw new IOException("Extensão não suportada");
            }
            File copia = File.createTempFile("amostra-", extensao, getCacheDir());
            String informacao;
            try {
                try (InputStream origem = getContentResolver().openInputStream(endereco);
                        OutputStream destino = new FileOutputStream(copia)) {
                    copiar(origem, destino);
                }
                informacao = sessao().callAttr("carregar", copia.getAbsolutePath(), nome).toString();
            } catch (Exception erro) {
                copia.delete();
                throw erro;
            }
            Bitmap previa = lerPrevia();
            return () -> {
                temImagem = true;
                arquivo.setText(informacao);
                imagem.exibir(previa, true);
                vazio.setVisibility(View.GONE);
                numero.setText("0");
                amostra.setText("");
                observacoes.setText("");
                estado.setText("Toque para marcar. Use dois dedos para ampliar.");
                telas[0].smoothScrollTo(0, 0);
            };
        });
    }

    private boolean exigirImagem() {
        if (temImagem) return true;
        avisar(SEM_IMAGEM);
        return false;
    }

    private int lerInteiro(EditText campo, int minimo, int maximo) {
        int valor;
        try {
            valor = Integer.parseInt(campo.getText().toString().trim());
        } catch (NumberFormatException erro) {
            valor = -1;
        }
        if (valor >= minimo && valor <= maximo) return valor;
        campo.setError("Informe um inteiro entre " + minimo + " e " + maximo + ".");
        return -1;
    }

    private void marcar(int x, int y) {
        int limite = lerInteiro(distancia, 0, 100);
        if (limite >= 0) editar("marcar", x, y, limite);
    }

    private void editarComDistancia(String metodo) {
        int limite = lerInteiro(distancia, 0, 100);
        if (limite >= 0) editar(metodo, limite);
    }

    private void detectar() {
        int brilho = lerInteiro(limiar, 0, 255);
        int menor = lerInteiro(minima, 1, Integer.MAX_VALUE);
        int maior = lerInteiro(maxima, 0, Integer.MAX_VALUE);
        if (brilho < 0 || menor < 0 || maior < 0) return;
        if (maior > 0 && maior < menor) {
            maxima.setError("Use 0 ou uma área maior ou igual à área mínima.");
            return;
        }
        editar("detectar", brilho, claras.isChecked(), menor, maior);
    }

    private void editar(String metodo, Object... argumentos) {
        if (ocupado || !exigirImagem()) return;
        if (metodo.equals("detectar")) estado.setText("Detectando regiões…");
        executar("Não foi possível atualizar a contagem.", () -> {
            String mensagem = sessao().callAttr(metodo, argumentos).toString();
            Bitmap previa = lerPrevia();
            String total = sessao().callAttr("total").toString();
            return () -> {
                imagem.exibir(previa, false);
                numero.setText(total);
                estado.setText(mensagem);
                if (metodo.equals("detectar") || metodo.equals("incorporar") || metodo.equals("descartar")) {
                    telas[0].smoothScrollTo(0, 0);
                }
            };
        });
    }

    private Bitmap lerPrevia() throws IOException {
        Bitmap previa = BitmapFactory.decodeFile(sessao().callAttr("previa").toString());
        if (previa == null) throw new IOException("Falha na leitura da prévia");
        return previa;
    }

    private void confirmarLimpeza() {
        if (ocupado || !exigirImagem()) return;
        new AlertDialog.Builder(this).setMessage("Limpar as marcações e sugestões desta imagem?")
            .setNegativeButton("Cancelar", null).setPositiveButton("Limpar", (d, b) -> editar("limpar")).show();
    }

    private void salvar() {
        if (ocupado || !exigirImagem()) return;
        String nome = amostra.getText().toString().trim();
        if (nome.isEmpty()) {
            amostra.setError("Informe o nome da amostra.");
            amostra.requestFocus();
            return;
        }
        String notas = observacoes.getText().toString();
        executar("Não foi possível salvar a análise.", () -> {
            sessao().callAttr("salvar", nome, notas);
            return () -> avisar("Análise salva. Consulte a aba Histórico.");
        });
    }

    private void atualizarHistorico() {
        executar("Não foi possível ler o histórico.", () -> {
            JSONArray registros = new JSONArray(sessao().callAttr("historico").toString());
            return () -> {
                historico.removeAllViews();
                comEspaco(historico, texto("Análises registradas", 22, MARINHO, true));
                if (registros.length() == 0) comEspaco(historico, texto("Nenhuma análise registrada.", 15, CINZA, false));
                for (int i = 0; i < registros.length(); i++) {
                    JSONObject registro = registros.optJSONObject(i);
                    String id = registro.optString("id");
                    LinearLayout linha = cartao();
                    comEspaco(linha, texto(registro.optString("amostra"), 17, MARINHO, true));
                    String detalhe = registro.optInt("total") + " células · " + registro.optString("data")
                        + "\n" + registro.optString("imagem");
                    comEspaco(linha, texto(detalhe, 14, CINZA, false));
                    comEspaco(linha, botao("Ver análise", false, () -> consultar(id)));
                    comEspaco(historico, linha);
                }
                comEspaco(historico, botao("Exportar resultados (CSV)", true, () -> escolherExportacao(CSV)));
            };
        });
    }

    private void consultar(String id) {
        executar("Não foi possível abrir a análise.", () -> {
            JSONObject registro = new JSONObject(sessao().callAttr("consultar", id).toString());
            String arquivoPrevia = registro.optString("previa");
            Bitmap previa = arquivoPrevia.isEmpty() ? null : BitmapFactory.decodeFile(arquivoPrevia);
            return () -> {
                LinearLayout conteudo = painelPagina();
                comEspaco(conteudo, texto(registro.optString("detalhes"), 15, MARINHO, false));
                if (previa != null) {
                    ImageView miniatura = new ImageView(this);
                    miniatura.setImageBitmap(previa);
                    miniatura.setAdjustViewBounds(true);
                    miniatura.setMaxHeight(dp(300));
                    miniatura.setContentDescription("Imagem da análise com os marcadores salvos");
                    comEspaco(conteudo, miniatura);
                }
                String pontos = registro.optString("pontos");
                if (!pontos.isEmpty()) {
                    comEspaco(conteudo, botao("Ver coordenadas (X, Y)", false, () -> {
                        LinearLayout lista = painelPagina();
                        lista.addView(texto(pontos, 15, MARINHO, false));
                        new AlertDialog.Builder(this).setTitle("Coordenadas (X, Y)").setView(rolagem(lista))
                            .setPositiveButton("Fechar", null).show();
                    }));
                }
                new AlertDialog.Builder(this).setTitle(registro.optString("titulo"))
                    .setView(rolagem(conteudo)).setPositiveButton("Fechar", null).show();
            };
        });
    }

    private void atualizarResultados() {
        executar("Não foi possível calcular os resultados.", () -> {
            JSONArray totais = new JSONArray(sessao().callAttr("resultados").toString());
            return () -> {
                resultados.removeAllViews();
                comEspaco(resultados, texto("Resultados", 22, MARINHO, true));
                String[] nomes = {"Células da análise atual", "Análises registradas", "Células nas análises salvas"};
                for (int i = 0; i < nomes.length; i++) {
                    LinearLayout indicador = cartao();
                    indicador.addView(texto(nomes[i], 15, CINZA, true));
                    indicador.addView(texto(totais.optString(i), 35, AZUL, true));
                    comEspaco(resultados, indicador);
                }
            };
        });
    }

    private void escolherExportacao(int tipo) {
        if (ocupado || (tipo == PNG && !exigirImagem())) return;
        Intent criar = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        criar.addCategory(Intent.CATEGORY_OPENABLE);
        criar.setType(tipo == PNG ? "image/png" : "text/csv");
        criar.putExtra(Intent.EXTRA_TITLE, tipo == PNG ? "imagem-anotada.png" : "resultados-cellcount.csv");
        startActivityForResult(criar, tipo);
    }

    private void gravarExportacao(Uri endereco, int tipo) {
        if (tipo == PNG && !exigirImagem()) return;
        executar("Não foi possível gravar o arquivo exportado.", () -> {
            String extensao = tipo == PNG ? "png" : "csv";
            File arquivoTemporario = File.createTempFile("exportacao-", "." + extensao, getCacheDir());
            try {
                sessao().callAttr("exportar", extensao, arquivoTemporario.getAbsolutePath());
                try (InputStream origem = new FileInputStream(arquivoTemporario);
                        OutputStream destino = getContentResolver().openOutputStream(endereco, "wt")) {
                    copiar(origem, destino);
                }
            } finally {
                arquivoTemporario.delete();
            }
            return () -> avisar("Arquivo exportado.");
        });
    }

    private void copiar(InputStream origem, OutputStream destino) throws IOException {
        if (origem == null || destino == null) throw new IOException("Arquivo indisponível");
        byte[] parte = new byte[32768];
        int tamanho;
        while ((tamanho = origem.read(parte)) != -1) destino.write(parte, 0, tamanho);
    }

    private void avisar(String mensagem) {
        if (estado != null) estado.setText(mensagem);
        Toast.makeText(this, mensagem, Toast.LENGTH_SHORT).show();
    }

    private int dp(int medida) { return Math.round(medida * getResources().getDisplayMetrics().density); }

    private LinearLayout coluna() {
        LinearLayout grupo = new LinearLayout(this);
        grupo.setOrientation(LinearLayout.VERTICAL);
        return grupo;
    }

    private LinearLayout linha() {
        LinearLayout grupo = new LinearLayout(this);
        grupo.setOrientation(LinearLayout.HORIZONTAL);
        return grupo;
    }

    private ScrollView rolagem(LinearLayout conteudo) {
        ScrollView tela = new ScrollView(this);
        tela.setFillViewport(true);
        tela.addView(conteudo);
        return tela;
    }

    private LinearLayout painelPagina() {
        LinearLayout painel = coluna();
        margemInterna(painel, 14, 10);
        return painel;
    }

    private LinearLayout cartao() {
        LinearLayout cartao = coluna();
        margemInterna(cartao, 12, 10);
        cartao.setBackground(fundo(Color.WHITE, 16, LINHA));
        return cartao;
    }

    private void margemInterna(View vista, int horizontal, int vertical) {
        vista.setPadding(dp(horizontal), dp(vertical), dp(horizontal), dp(vertical));
    }

    private void comEspaco(LinearLayout pai, View vista) {
        LinearLayout.LayoutParams parametros = new LinearLayout.LayoutParams(-1, -2);
        parametros.bottomMargin = dp(8);
        pai.addView(vista, parametros);
    }

    private void adicionarNaLinha(LinearLayout pai, View vista) {
        LinearLayout.LayoutParams parametros = new LinearLayout.LayoutParams(0, -2, 1);
        if (pai.getChildCount() > 0) parametros.leftMargin = dp(6);
        pai.addView(vista, parametros);
    }

    private GradientDrawable fundo(int cor, int raio, int borda) {
        GradientDrawable resultado = new GradientDrawable();
        resultado.setColor(cor);
        resultado.setCornerRadius(dp(raio));
        resultado.setStroke(dp(1), borda);
        return resultado;
    }

    private TextView texto(String conteudo, int tamanho, int cor, boolean destaque) {
        TextView campo = new TextView(this);
        campo.setText(conteudo);
        campo.setTextSize(tamanho);
        campo.setTextColor(cor);
        if (destaque) campo.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return campo;
    }

    private Button botao(String titulo, boolean principal, Runnable acao) {
        Button botao = new Button(this);
        botao.setAllCaps(false);
        botao.setText(titulo);
        botao.setTextSize(14);
        botao.setMinWidth(0);
        botao.setMinimumWidth(0);
        botao.setMinHeight(dp(46));
        margemInterna(botao, 5, 6);
        pintarBotao(botao, principal);
        botao.setOnClickListener(v -> acao.run());
        return botao;
    }

    private void pintarBotao(Button botao, boolean principal) {
        int cor = principal ? AZUL : 0xffeaf1fb;
        botao.setTextColor(principal ? Color.WHITE : MARINHO);
        botao.setBackground(new RippleDrawable(ColorStateList.valueOf(0x302456c5), fundo(cor, 11, cor), null));
    }

    private EditText campo(LinearLayout painel, String rotulo, String inicial, int tipo) {
        TextView etiqueta = texto(rotulo, 14, CINZA, true);
        EditText entrada = new EditText(this);
        entrada.setId(View.generateViewId());
        etiqueta.setLabelFor(entrada.getId());
        entrada.setInputType(tipo);
        entrada.setTextColor(MARINHO);
        entrada.setTextSize(16);
        entrada.setText(inicial);
        painel.addView(etiqueta);
        comEspaco(painel, entrada);
        return entrada;
    }

    @Override protected void onDestroy() {
        fila.shutdown();
        super.onDestroy();
    }
}
