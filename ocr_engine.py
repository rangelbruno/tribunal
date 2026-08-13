"""Motor de OCR usado para gerar PDFs pesquisáveis.

A estratégia é sempre a mesma: renderiza a página como imagem, reconhece as
palavras com suas coordenadas e escreve essas palavras de volta no PDF original
com o modo de renderização invisível. O PDF continua visualmente idêntico, mas
passa a ter texto selecionável e pesquisável.

Prioriza o Tesseract (muito mais rápido e paralelizável) e cai automaticamente
para o EasyOCR quando o Tesseract não está instalado na máquina.
"""

from __future__ import annotations

import io
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import fitz  # PyMuPDF

# Páginas com pelo menos esta quantidade de caracteres são consideradas
# "já pesquisáveis" e podem ser puladas.
MIN_TEXT_CHARS = 20

# Fonte base-14 do PDF: não precisa ser embutida e cobre o português.
INVISIBLE_FONT = "helv"

# Caminhos onde o instalador do Tesseract costuma colocar o executável no Windows.
_WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Tesseract-OCR\tesseract.exe"),
)


@dataclass(frozen=True)
class Line:
    """Uma linha reconhecida, em pontos do espaço nativo da página.

    O texto é gravado por linha, e não palavra a palavra: assim os espaços entre
    as palavras são os de verdade e a busca por frases inteiras funciona.
    """

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class PdfResult:
    """Resultado do processamento de um PDF."""

    data: bytes
    pages_total: int
    pages_ocr: int
    pages_skipped: int
    words: int
    engine: str


# --------------------------------------------------------------------------- #
# Detecção de motor
# --------------------------------------------------------------------------- #


def find_tesseract() -> str | None:
    """Retorna o caminho do executável do Tesseract, ou None se não houver."""
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and os.path.isfile(env_path):
        return env_path

    found = shutil.which("tesseract")
    if found:
        return found

    for candidate in _WINDOWS_TESSERACT_PATHS:
        if candidate and os.path.isfile(candidate):
            return candidate

    return None


def _configure_pytesseract() -> bool:
    """Aponta o pytesseract para o executável encontrado. False se indisponível."""
    cmd = find_tesseract()
    if not cmd:
        return False
    try:
        import pytesseract
    except ImportError:
        return False
    pytesseract.pytesseract.tesseract_cmd = cmd
    return True


def tesseract_languages() -> list[str]:
    """Idiomas instalados no Tesseract. Lista vazia se ele não estiver disponível."""
    if not _configure_pytesseract():
        return []
    try:
        import pytesseract

        return sorted(lang for lang in pytesseract.get_languages(config="") if lang != "osd")
    except Exception:
        return []


def default_language(available: list[str]) -> str:
    """Melhor combinação de idiomas disponível para documentos brasileiros."""
    if "por" in available and "eng" in available:
        return "por+eng"
    if "por" in available:
        return "por"
    return "eng"


def available_engine() -> str:
    """'tesseract' quando instalado, senão 'easyocr'."""
    return "tesseract" if _configure_pytesseract() else "easyocr"


# --------------------------------------------------------------------------- #
# EasyOCR (fallback)
# --------------------------------------------------------------------------- #

_easyocr_reader = None
_easyocr_lock = threading.Lock()


def get_easyocr_reader():
    """Carrega o leitor do EasyOCR uma única vez por processo."""
    global _easyocr_reader
    with _easyocr_lock:
        if _easyocr_reader is None:
            import easyocr

            _easyocr_reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
        return _easyocr_reader


# --------------------------------------------------------------------------- #
# OCR de uma página
# --------------------------------------------------------------------------- #


def _pixmap_to_pil(pix: fitz.Pixmap):
    from PIL import Image

    mode = "L" if pix.n == 1 else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def _rotation_transpose(rotation: int):
    """Operação do PIL que gira a imagem no mesmo sentido que o leitor de PDF."""
    from PIL import Image

    # /Rotate do PDF é horário; ROTATE_* do PIL é anti-horário.
    return {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }[rotation]


def _unrotate_box(
    x0: float, y0: float, x1: float, y1: float, rotation: int, width: float, height: float
) -> tuple[float, float, float, float]:
    """Leva um bbox da imagem girada (legível) de volta para a imagem nativa.

    `width`/`height` são as dimensões da imagem NATIVA, antes do giro.
    """
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    if rotation == 90:
        mapped = [(y, height - x) for x, y in corners]
    elif rotation == 180:
        mapped = [(width - x, height - y) for x, y in corners]
    elif rotation == 270:
        mapped = [(width - y, x) for x, y in corners]
    else:
        mapped = list(corners)

    xs = [point[0] for point in mapped]
    ys = [point[1] for point in mapped]
    return min(xs), min(ys), max(xs), max(ys)


def _ocr_tesseract(image, lang: str) -> list[tuple[str, float, float, float, float]]:
    import pytesseract
    from pytesseract import Output

    data = pytesseract.image_to_data(
        image,
        lang=lang,
        output_type=Output.DICT,
        config="--oem 1 --psm 3 -c preserve_interword_spaces=1",
    )

    # Agrupa as palavras na linha a que pertencem, preservando a ordem de leitura.
    grouped: dict[tuple[int, int, int], list] = {}
    for i, raw in enumerate(data["text"]):
        text = (raw or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        x, y = data["left"][i], data["top"][i]
        w, h = data["width"][i], data["height"][i]
        if w <= 0 or h <= 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        grouped.setdefault(key, []).append((x, text, x, y, x + w, y + h))

    lines: list[tuple[str, float, float, float, float]] = []
    for parts in grouped.values():
        parts.sort(key=lambda item: item[0])
        text = " ".join(item[1] for item in parts)
        lines.append(
            (
                text,
                min(item[2] for item in parts),
                min(item[3] for item in parts),
                max(item[4] for item in parts),
                max(item[5] for item in parts),
            )
        )
    return lines


def _ocr_easyocr(image) -> list[tuple[str, float, float, float, float]]:
    import numpy as np

    reader = get_easyocr_reader()
    results = reader.readtext(np.asarray(image), detail=1, paragraph=False)

    words: list[tuple[str, float, float, float, float]] = []
    for box, text, conf in results:
        text = (text or "").strip()
        if not text or conf < 0.2:
            continue
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        words.append((text, min(xs), min(ys), max(xs), max(ys)))
    return words


def ocr_page(page: fitz.Page, engine: str, lang: str, dpi: int) -> list[Line]:
    """Reconhece as linhas de uma página, em pontos do espaço NATIVO da página.

    Páginas com /Rotate são normalizadas: renderizamos sem rotação, giramos a
    imagem só para o OCR conseguir ler e devolvemos os bboxes ao espaço nativo.
    Assim a camada de texto acompanha o conteúdo quando o leitor aplica a rotação.
    """
    rotation = page.rotation
    if rotation:
        page.set_rotation(0)
    try:
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
        native_w, native_h = pix.width, pix.height
        if native_w == 0 or native_h == 0:
            return []

        image = _pixmap_to_pil(pix)
        pix = None  # libera a cópia crua o quanto antes
        if rotation:
            image = image.transpose(_rotation_transpose(rotation))

        raw = _ocr_tesseract(image, lang) if engine == "tesseract" else _ocr_easyocr(image)

        scale_x = page.rect.width / native_w
        scale_y = page.rect.height / native_h
    finally:
        if rotation:
            page.set_rotation(rotation)

    lines = []
    for text, x0, y0, x1, y1 in raw:
        if rotation:
            x0, y0, x1, y1 = _unrotate_box(x0, y0, x1, y1, rotation, native_w, native_h)
        lines.append(Line(text, x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y))
    return lines


# --------------------------------------------------------------------------- #
# Escrita da camada invisível
# --------------------------------------------------------------------------- #


def insert_invisible_text(page: fitz.Page, lines: list[Line]) -> int:
    """Escreve as linhas na página com render_mode=3 (invisível).

    Retorna quantas palavras foram gravadas.
    """
    if not lines:
        return 0

    # As linhas chegam em coordenadas nativas (ver ocr_page), então a rotação é
    # zerada durante a escrita e devolvida em seguida — o PDF salvo mantém o
    # /Rotate original e o texto gira junto com o conteúdo.
    rotation = page.rotation
    if rotation:
        page.set_rotation(0)

    # Em páginas de 90°/270° as linhas ficam na vertical no espaço nativo, então
    # o texto precisa ser escrito girado e ancorado no canto inferior direito.
    vertical = rotation in (90, 270)
    text_rotation = 90 if vertical else 0

    written = 0
    try:
        for line in lines:
            width = line.x1 - line.x0
            height = line.y1 - line.y0
            if width <= 0 or height <= 0:
                continue

            length, thickness = (height, width) if vertical else (width, height)

            # Ajusta o corpo da fonte para que a linha ocupe a mesma extensão do
            # trecho reconhecido — é o que faz a seleção do texto bater com a imagem.
            measured = fitz.get_text_length(line.text, fontname=INVISIBLE_FONT, fontsize=100)
            if measured <= 0:
                continue
            fontsize = min(100 * length / measured, thickness * 1.4)
            if fontsize < 0.5:
                continue

            # A baseline fica um pouco dentro do bbox, que inclui os descendentes.
            inset = thickness * 0.2
            point = (
                fitz.Point(line.x1 - inset, line.y1)
                if vertical
                else fitz.Point(line.x0, line.y1 - inset)
            )

            try:
                page.insert_text(
                    point,
                    line.text,
                    fontname=INVISIBLE_FONT,
                    fontsize=fontsize,
                    rotate=text_rotation,
                    render_mode=3,
                )
            except Exception:
                # Uma linha problemática não deve derrubar o documento inteiro.
                continue
            written += len(line.text.split())
    finally:
        if rotation:
            page.set_rotation(rotation)

    return written


# --------------------------------------------------------------------------- #
# Pipeline por documento
# --------------------------------------------------------------------------- #


def make_searchable_pdf(
    pdf_bytes: bytes,
    *,
    engine: str,
    lang: str = "por+eng",
    dpi: int = 200,
    skip_text_pages: bool = True,
    workers: int = 4,
    progress_cb=None,
) -> PdfResult:
    """Gera a versão pesquisável de um PDF.

    `progress_cb(feitas, total)` é chamado sempre na thread que invocou a função,
    então pode atualizar a interface com segurança.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = doc.page_count

        todo: list[int] = []
        for number in range(total_pages):
            has_text = len(doc[number].get_text("text").strip()) >= MIN_TEXT_CHARS
            if skip_text_pages and has_text:
                continue
            todo.append(number)

        if progress_cb:
            progress_cb(0, len(todo))

        results: dict[int, list[Line]] = {}

        # O EasyOCR carrega modelos pesados e não ganha nada com threads.
        effective_workers = max(1, workers) if engine == "tesseract" else 1

        if not todo:
            pass
        elif effective_workers == 1:
            for done, number in enumerate(todo, start=1):
                results[number] = ocr_page(doc[number], engine, lang, dpi)
                if progress_cb:
                    progress_cb(done, len(todo))
        else:
            # Um fitz.Document não é thread-safe, então cada thread abre o seu.
            thread_state = threading.local()
            opened: list[fitz.Document] = []
            opened_lock = threading.Lock()

            def worker(number: int) -> tuple[int, list[Line]]:
                own = getattr(thread_state, "doc", None)
                if own is None:
                    own = fitz.open(stream=pdf_bytes, filetype="pdf")
                    thread_state.doc = own
                    with opened_lock:
                        opened.append(own)
                return number, ocr_page(own[number], engine, lang, dpi)

            try:
                with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                    futures = [pool.submit(worker, number) for number in todo]
                    for done, future in enumerate(as_completed(futures), start=1):
                        number, page_lines = future.result()
                        results[number] = page_lines
                        if progress_cb:
                            progress_cb(done, len(todo))
            finally:
                for extra in opened:
                    extra.close()

        written = 0
        for number, page_lines in results.items():
            written += insert_invisible_text(doc[number], page_lines)

        buffer = io.BytesIO()
        doc.save(buffer, garbage=3, deflate=True)

        return PdfResult(
            data=buffer.getvalue(),
            pages_total=total_pages,
            pages_ocr=len(todo),
            pages_skipped=total_pages - len(todo),
            words=written,
            engine=engine,
        )
    finally:
        doc.close()
