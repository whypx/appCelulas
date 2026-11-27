import sys
from asyncio import get_running_loop, to_thread
from pathlib import Path
from shutil import copyfile
from tempfile import NamedTemporaryFile, TemporaryDirectory

import toga

from .contador import ContadorCelulas


class Arquivos:
    def __init__(self, aplicativo):
        self.app = aplicativo

    async def escolher(self, cache):
        if sys.platform == "android":
            uri = await self.seletor_android()
            if uri is None:
                return None
            return await to_thread(self.importar_android, uri, cache)

        original = await self.app.main_window.dialog(toga.OpenFileDialog(
            "Abrir imagem", file_types=["png", "jpg", "jpeg", "tif", "tiff"],
        ))
        if original is None:
            return None
        copia = self.criar_copia(cache, original.name)
        try:
            await to_thread(copyfile, original, copia)
        except OSError:
            copia.unlink(missing_ok=True)
            raise
        return copia, original.name

    def criar_copia(self, cache, nome):
        extensao = Path(nome).suffix.lower()
        if extensao not in ContadorCelulas.FORMATOS:
            raise ValueError("Escolha uma imagem PNG, JPEG ou TIFF.")
        with NamedTemporaryFile(prefix="amostra-", suffix=extensao, dir=cache, delete=False) as arquivo:
            return Path(arquivo.name)

    async def exportar(self, sessao, tipo):
        nome = {"png": "cellcount-anotada.png", "csv": "cellcount-resultados.csv"}[tipo]
        if sys.platform == "android":
            uri = await self.seletor_android(nome)
            if uri is None:
                return False
            with TemporaryDirectory(dir=sessao.cache) as pasta:
                caminho = Path(pasta) / nome
                await to_thread(sessao.exportar, tipo, caminho)
                await to_thread(self.exportar_android, caminho, uri)
        else:
            caminho = await self.app.main_window.dialog(toga.SaveFileDialog(
                "Salvar exportação", nome, file_types=[tipo],
            ))
            if caminho is None:
                return False
            await to_thread(sessao.exportar, tipo, caminho)
        return True

    async def seletor_android(self, nome=None):
        from android.app import Activity
        from android.content import Intent

        if nome is None:
            pedido = Intent(Intent.ACTION_OPEN_DOCUMENT)
            pedido.setType("*/*")
        else:
            pedido = Intent(Intent.ACTION_CREATE_DOCUMENT)
            pedido.setType("image/png" if nome.endswith(".png") else "text/csv")
            pedido.putExtra(Intent.EXTRA_TITLE, nome)
        pedido.addCategory(Intent.CATEGORY_OPENABLE)

        futuro = get_running_loop().create_future()

        def receber(codigo, resposta):
            if not futuro.done():
                uri = resposta.getData() if codigo == Activity.RESULT_OK and resposta else None
                futuro.set_result(uri)

        self.app._impl.start_activity(pedido, on_complete=receber)
        return await futuro

    def importar_android(self, uri, cache):
        from android.provider import OpenableColumns
        from android.webkit import MimeTypeMap
        from java.io import FileOutputStream

        resolver = self.app._impl.native.getContentResolver()
        cursor = resolver.query(uri, [OpenableColumns.DISPLAY_NAME], None, None, None)
        nome = None
        if cursor is not None:
            try:
                if cursor.moveToFirst() and not cursor.isNull(0):
                    nome = str(cursor.getString(0))
            finally:
                cursor.close()
        if not nome:
            mime = resolver.getType(uri)
            extensao = MimeTypeMap.getSingleton().getExtensionFromMimeType(mime)
            nome = f"imagem.{extensao}"
        copia = self.criar_copia(cache, nome)
        try:
            self.transferir(resolver.openInputStream(uri), lambda: FileOutputStream(str(copia)))
        except Exception:
            copia.unlink(missing_ok=True)
            raise
        return copia, nome

    def exportar_android(self, caminho, uri):
        from java.io import FileInputStream

        resolver = self.app._impl.native.getContentResolver()
        self.transferir(FileInputStream(str(caminho)), lambda: resolver.openOutputStream(uri, "wt"))

    def transferir(self, origem, abrir_destino):
        from java import jarray, jbyte

        if origem is None:
            raise OSError("Não foi possível abrir o arquivo de origem.")
        try:
            destino = abrir_destino()
            if destino is None:
                raise OSError("Não foi possível abrir o destino da exportação.")
            try:
                bloco = jarray(jbyte)(32768)
                lidos = origem.read(bloco)
                while lidos != -1:
                    destino.write(bloco, 0, lidos)
                    lidos = origem.read(bloco)
            finally:
                destino.close()
        finally:
            origem.close()
