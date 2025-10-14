import qrcode
import textwrap
import pandas as pd
from typing import cast
from urllib.parse import urlencode
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from qrcode.image.styledpil import StyledPilImage
from reportlab.pdfbase.pdfmetrics import stringWidth
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

from PIL import Image
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_H
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QProgressBar, QProgressBar, QLabel

class ProgressBarState:     # state is set by main window when a file is loaded.
    def __init__(self, progressBar: QProgressBar, label: QLabel):
        self.progressBar: QProgressBar = progressBar
        self.label: QLabel = label


HRC_LOGO_WIDTH = 62 * mm
HRC_LOGO_HEIGHT = 24 * mm

LOGO = Image.open("./assets/hrc-logo-simplified.png").convert("RGBA")
LOGO_SIZE_RATIO: float = 0.3
LOGO_WIDTH, LOGO_HEIGHT = LOGO.size
LOGO_WIDTH, LOGO_HEIGHT = int(LOGO_WIDTH*LOGO_SIZE_RATIO), int(LOGO_HEIGHT*LOGO_SIZE_RATIO)
LOGO = LOGO.resize((LOGO_WIDTH, LOGO_HEIGHT))


def getUrlFrom(row: pd.Series):
    params = { "Catégorie": "Salle de Réunion" }     # will be overwritten if equipments CSV was provided, otherwise it's meeting rooms.
    
    for col in row.index: 
        params[col] = cast(str, row[col])

    encoded_query = urlencode(params, encoding='utf-8')
    return "https://apps-hrc.adi.adies.lan/mailer/new-ticket?" + encoded_query


def genLargeVerticalQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str = "./output/largeVerticalQRs.pdf", qrCaption: str = ""): 
    progressBar.progressBar.setValue(0)
    
    print("genLargeVerticalQRPDFsFor")
    QRCodeSize = 100 * mm
    width, height = A4
    fontSize, charsPerLine = 16, 40
    
    xStart, yStart = 15 * mm, height - 33 * mm
    x, y = xStart, yStart
    
    c = canvas.Canvas(outputPath + "/largeVerticalQRs.pdf", pagesize=A4)
    
    count = 0
    
    for index, (_, row) in enumerate(entries.iterrows()):
        
        c.drawImage("./assets/hrc-logo.jpg", x, y, width=1.25*HRC_LOGO_WIDTH, height=1.25*HRC_LOGO_HEIGHT)
        
        y -= QRCodeSize
        x -= 12 * mm
        
        url = getUrlFrom(row)
        
        updateProgressBar(index, entries, url, progressBar)
        
        c.drawImage(getQRImageReaderFromRow(url), x, y, width=QRCodeSize, height=QRCodeSize)                    # draw the QR code
        
        drawText(c, row, x, QRCodeSize / 2, y, fontSize, charsPerLine, is_eq_csv, qrCaption, QRCodeSize - 10 * mm, fontSize, max_lines=2)
        
        count += 1
        
        if count % 4 == 0:
            c.showPage()
            x, y = xStart, yStart
            count = 0
        else:
            # manually hardcore all QR code positions (coded to fit to a 3483 sticker sheet)
            if count == 1:
                x, y = 119 * mm, yStart
            elif count == 2:
                x, y = 15 * mm, height - 182 * mm
            elif count == 3:
                x, y = 119 * mm, height - 182 * mm
    
    progressBar.progressBar.setValue(100)
    c.save()
    print(f"LOG: PDF saved as: {outputPath}")


def genMediumHorizontalQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str = "./output/mediumHoriQRs.pdf", qrCaption: str = ""): # entries (code, model, image)
    progressBar.progressBar.setValue(0)
    
    print("genMediumHorizontalQRPDFsFor")
    QRCodeSize = 44 * mm
    width, height = A4
    fontSize, charsPerLine = 12, 30
    xStart, yStart = 3 * mm, height - 28 * mm
    x, y = xStart, yStart
    
    c = canvas.Canvas(outputPath + "/mediumHoriQRs.pdf", pagesize=A4)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        c.drawImage("./assets/hrc-logo.jpg", x, y, width=0.9*HRC_LOGO_WIDTH, height=0.9*HRC_LOGO_HEIGHT)
        
        
        yText = drawText(c, row, x, 27*mm, y - fontSize, fontSize, charsPerLine, is_eq_csv, qrCaption, HRC_LOGO_WIDTH - 10 * mm, fontSize, max_lines=3)
        
        x += 55*mm                  # move cursor bottom right of text to draw QR code
        y = yText - 3 * mm
        
        url = getUrlFrom(row)
        updateProgressBar(index, entries, url, progressBar)
        c.drawImage(getQRImageReaderFromRow(url), x, y, width=QRCodeSize, height=QRCodeSize)
        
        count += 1
        
        y = yStart - (count // 2) * 49 * mm   # (count // 2) is the line number we're on
        
        if count % 2 != 0:          # i.e. we're in the second column
            x = 105*mm + xStart     # middle point + margin
        else:
            x = xStart
        
        if count == 12:
            c.showPage()
            x, y = xStart, yStart
            count = 0
    
    progressBar.progressBar.setValue(100)
    c.save()
    print(f"LOG: PDF saved as :{outputPath}")   


def genSmallSquareQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str = "./output/largeVerticalQRs.pdf", qrCaption: str = ""):
    progressBar.progressBar.setValue(0)
    
    print("genSmallSquareQRPDFsFor")
    QRCodeSize = 60 * mm
    width, height = A4
    fontSize, charsPerLine = 10, 40
    xStart, yStart = 2.5 * mm, height - 10 * mm - 58 * mm                                       # top-margin minus 5 height of sticker square (Zweckform 3661)
    x, y = xStart, yStart
    
    c = canvas.Canvas(outputPath + "/smallSquareQRs.pdf", pagesize=A4)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        url = getUrlFrom(row)
        
        updateProgressBar(index, entries, url, progressBar)
        
        c.drawImage(getQRImageReaderFromRow(url, True), x, y, width=QRCodeSize, height=QRCodeSize)
        
        drawText(c, row, x, 30*mm, y, fontSize, charsPerLine, is_eq_csv, qrCaption, QRCodeSize, fontSize, max_lines=2)
        
        count += 1
        y = yStart - (count // 3) * 70 * mm   # (count // 3) is the line number we're on
        
        if count % 3 != 0:                    # i.e. we just drew the qr code in the third column
            x += 70*mm + xStart                # width of square + margin
        else:
            x = xStart
        
        if count == 12:
            c.showPage()
            x, y = xStart, yStart
            count = 0
    
    progressBar.progressBar.setValue(100)
    
    c.save()
    print(f"LOG: PDF saved as :{outputPath}")   
        

def getQRImageReaderFromRow(url: str, embbed_logo: bool = False) -> ImageReader:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_L)
    qr.add_data(url)
    
    qr_code: Image.Image = qr.make_image(
        image_factory=StyledPilImage, 
        module_drawer=RoundedModuleDrawer(),
        eye_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=(1, 158, 227))
    ).get_image()
    
    if embbed_logo:
        qr_width, qr_height = qr_code.size
        pos = ( (qr_width - LOGO_WIDTH) // 2, (qr_height - LOGO_HEIGHT) // 2 )
        
        qr_code.paste(LOGO, pos, LOGO)
    
    return ImageReader(qr_code)

# we need the min max wrap width such as no fucking [...] is inserted.

def getOptimalWrapWidthForText(text: str, max_lines: int = 2):
    width = len("[...]")
    while True:
        wLines = textwrap.wrap(text, width=width, max_lines=max_lines)
        print(wLines, width)
        if wLines[-1].find("[...]") == -1:
            return width
        else:
            width += 1

def drawText(c: canvas.Canvas, row: pd.Series, x: float, x_margin: float, yText: float, fontSize: float, charsPerLine: int, is_eq_csv: bool, qrCaption: str, maxTextWidth: float, maxFontSize: float, max_lines: int) -> float:
    pdfmetrics.registerFont(TTFont('NettoVDR', './assets/NettoOffc.ttf'))
    pdfmetrics.registerFont(TTFont('NettoBold', './assets/NettoOffc-Bold.ttf'))
    
    optimalLineWidth = getOptimalWrapWidthForText(qrCaption, max_lines=max_lines)
    wLines: list[str] = textwrap.wrap(qrCaption, width=optimalLineWidth, max_lines=max_lines)
    
    line_lengths = [len(line) for line in wLines]
    idx = line_lengths.index(max(line_lengths))
    
    fontSize = fit_text_to_width(wLines[idx], "NettoVDR", max_width=maxTextWidth, max_font_size=maxFontSize)
    
    c.setFont("NettoVDR", fontSize)   
    # textwrap.wrap(qrCaption, width=charsPerLine, max_lines=max_lines, break_long_words=True)               # "wrap" caption to array of strings of max chars per entry
    
    for line in wLines:
        c.drawCentredString(x + x_margin, yText, line)
        yText -= fontSize
    
    modCodeMat = f"{row["Modèle"]} {row["Code matériel"]}"
    
    c.setFont("NettoBold", fontSize)
    if is_eq_csv:
        c.drawCentredString(x + x_margin, yText, modCodeMat)
    else:
        c.drawCentredString(x + x_margin, yText, f"Salle de Réunion {row["Numéro de Signalétique"]} {row["Localisation"]}")
    
    return yText

def split_string_at_middle(text: str) -> list[str]:
    lhalf, rhalf = text[:len(text) // 2], text[(len(text) // 2):]
    
    if lhalf[-1] == " " or rhalf[0] == " ": 
        return [lhalf, rhalf]
    else:
        return [lhalf + "-", rhalf]

def updateProgressBar(index: int, entries: pd.DataFrame, url: str, progressBar: ProgressBarState):
    value = round(100 * cast(int, index) / entries.shape[0])
    print(value)
    
    progressBar.label.setText(url)
    progressBar.progressBar.setValue(value)
    
    QCoreApplication.processEvents()                # keep ui responsive by processing events
    

def fit_text_to_width(text, font_name="Helvetica", max_width: float=200, max_font_size: float=20, min_font_size=4):
    """
    Find the largest font size such that `text` fits in `max_width`.

    Args:
        text (str): The text to fit.
        font_name (str): The ReportLab font name.
        max_width (float): Maximum allowed width (in points).
        max_font_size (float): Upper bound of font size search.
        min_font_size (float): Lower bound of font size search.

    Returns:
        float: The best font size fitting in max_width.
    """
    font_size = max_font_size
    while font_size >= min_font_size:
        text_width = stringWidth(text, font_name, font_size)
        if text_width <= max_width:
            return float(font_size)
        font_size -= 0.5  # decrease gradually (can also use binary search for speed)
    return float(min_font_size)