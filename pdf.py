##############################################################################
# A. Freeman 15/10/2024                         swissarthurfreeman@gmail.com #
# reportlab/python-qrcode based functions to generate PDFs following Avery   #
# Zweckform formats 3424, 3483 3661.                                         #
##############################################################################
import qrcode
import textwrap
import pandas as pd
from PIL import Image
from typing import cast
from urllib.parse import urlencode
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from PyQt6.QtCore import QCoreApplication
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from qrcode.constants import ERROR_CORRECT_L
from qrcode.image.styledpil import StyledPilImage
from reportlab.pdfbase.pdfmetrics import stringWidth
from qrcode.image.styles.colormasks import SolidFillColorMask
from PyQt6.QtWidgets import QProgressBar, QProgressBar, QLabel
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer


class ProgressBarState:     # state is set by main window when a file is loaded.
    def __init__(self, progressBar: QProgressBar, label: QLabel):
        self.progressBar: QProgressBar = progressBar
        self.label: QLabel = label


HRC_LOGO_WIDTH, HRC_LOGO_HEIGHT = 62 * mm, 24 * mm

LOGO = Image.open("./assets/hrc-logo-simplified.png").convert("RGBA")
LOGO_SIZE_RATIO: float = 0.3
LOGO_WIDTH, LOGO_HEIGHT = int(LOGO.size[0] * LOGO_SIZE_RATIO), int(LOGO.size[1] * LOGO_SIZE_RATIO)
LOGO = LOGO.resize((LOGO_WIDTH, LOGO_HEIGHT))
OPTIMAL_LINE_WIDTH = None

pdfmetrics.registerFont(TTFont('NettoVDR', './assets/NettoOffc.ttf'))
pdfmetrics.registerFont(TTFont('NettoBold', './assets/NettoOffc-Bold.ttf'))


def getUrlFrom(row: pd.Series):
    params = { "Catégorie": "Salle de Réunion" }     # will be overwritten if equipments CSV was provided, otherwise it's meeting rooms.
    
    for col in row.index: 
        params[col] = cast(str, row[col])

    encoded_query = urlencode(params, encoding='utf-8')
    return "https://apps-hrc.adi.adies.lan/mailer/new-ticket?" + encoded_query


def genPDFsWithAveryZweckform3483Format(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str, qrCaption: str): 
    """
    Generate a pdf containing QR codes for each row of `entries` using Avery Zweckform 3483 format (large vertical). Logo on top, QR 
    in middle, `qrCaption` underneath. If `is_eq_csv` is True, equipment info will be added as last line, otherwise, meeting room info. 
    `progressBar` is used to update the progress bar in the calling parent window. Sticker format is (width, height) = (10.4 cm, 14.7 cm)
    """
    progressBar.progressBar.setValue(0)
    
    QRCodeSize = 100 * mm
    _, height = A4
    
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
        drawText(c=c, row=row, x=x + QRCodeSize / 2, yText=y, is_eq_csv=is_eq_csv, qrCaption=qrCaption, maxTextWidth=QRCodeSize - 10 * mm, maxFontSize=16, max_lines=2)
        
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


def genPDFsWithAveryZweckform3424Format(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str, qrCaption: str):
    """
    Generate a pdf containing QR codes for each row of `entries` using Avery Zweckform 3424 format (medium size, horizontal). Logo top left, 
    `qrCaption` bottom left, QR to the right. If `is_eq_csv` is True, equipment info will be added as last line, otherwise, meeting room info. 
    `progressBar` is used to update the progress bar in the calling parent window. Sticker format is (width, height) = (10.4 cm, 4.8 cm)
    """
    progressBar.progressBar.setValue(0)
    
    QRCodeSize = 44 * mm
    _, height = A4
    xStart, yStart = 3 * mm, height - 26 * mm
    x, y = xStart, yStart
    maxFontSize = 12
    
    c = canvas.Canvas(outputPath + "/mediumHoriQRs.pdf", pagesize=A4)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        c.drawImage("./assets/hrc-logo.jpg", x, y, width=0.9*HRC_LOGO_WIDTH, height=0.9*HRC_LOGO_HEIGHT)
        drawText(c=c, row=row, x=x + 27*mm, yText=y - maxFontSize, is_eq_csv=is_eq_csv, qrCaption=qrCaption, maxTextWidth=HRC_LOGO_WIDTH - 10 * mm, maxFontSize=maxFontSize, max_lines=3)
        
        x += 55*mm                  # move cursor bottom right of text to draw QR code
        
        url = getUrlFrom(row)
        updateProgressBar(index, entries, url, progressBar)
        c.drawImage(getQRImageReaderFromRow(url), x, y - (QRCodeSize // 2) + 2 * mm, width=QRCodeSize, height=QRCodeSize)
        
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


def genPDFsWithAveryZweckform3661Format(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState, outputPath: str, qrCaption: str):
    """
    Generate a pdf containing QR codes for each row of `entries` using Avery Zweckform 3661 format (small squares). QR code at the top, `qrCaption` 
    underneath, If `is_eq_csv` is True, equipment info will be added as last line, otherwise, meeting room info. `progressBar` is used to update 
    the progress bar in the calling parent window. Sticker format is (width, height) = (6.9 cm, 6.7 cm)
    """
    progressBar.progressBar.setValue(0)
    
    QRCodeSize = 60 * mm
    _, height = A4
    xStart, yStart = 2.5 * mm, height - 10 * mm - 58 * mm                                       # top-margin minus 5 height of sticker square (Zweckform 3661)
    x, y = xStart, yStart
    
    c = canvas.Canvas(outputPath + "/smallSquareQRs.pdf", pagesize=A4)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        url = getUrlFrom(row)
        updateProgressBar(index, entries, url, progressBar)
        c.drawImage(getQRImageReaderFromRow(url, True), x, y, width=QRCodeSize, height=QRCodeSize)
        drawText(c=c, row=row, x=x + 30*mm, yText=y, is_eq_csv=is_eq_csv, qrCaption=qrCaption, maxTextWidth=QRCodeSize, maxFontSize=10, max_lines=2)
        
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


def getOptimalWrapWidthForText(text: str, max_lines: int = 2):
    """
    Retrieve the smallest largest text width such as no [...] placeholder
    is inserted in the text wrap. 
    """
    width = len("[...]")
    while True:
        wLines = textwrap.wrap(text, width=width, max_lines=max_lines)
        if wLines[-1].find("[...]") == -1:
            return width
        else:
            width += 1

MAX_LINES = None

def drawText(c: canvas.Canvas, row: pd.Series, x: float, yText: float, is_eq_csv: bool, qrCaption: str, maxTextWidth: float, maxFontSize: float, max_lines: int) -> float:
    """
    Draw provided text `qrCaption` centered at position x starting at height `yText`. `qrCaption` will be wrapped to a max of `max_lines` and it's 
    font size will be computed such as the longest wrapped line doesn't exceed `maxTextWidth` and is of maximum font size `maxFontSize`. `row` will 
    be used to write either **row[Modèle] row[Code matériel]** as last line or **Salle de Réunion row[Numéro de Signalétique] row[Localisation]**
    depending on `is_eq_csv`.
    """  
    wLines: list[str] = textwrap.wrap(qrCaption, width=getOptimalWrapWidthForText(qrCaption, max_lines=max_lines), max_lines=max_lines)   # wrap lines to max_lines
    wLines.append(
        f"{row["Modèle"]} {row["Code matériel"]}" if is_eq_csv else 
        f"Salle de Réunion {row["Numéro de Signalétique"]} {row["Localisation"]}"
    )
    
    line_lengths = [len(line) for line in wLines]
    idx = line_lengths.index(max(line_lengths))         # get index of longest line
    
    fontSize = fit_text_to_width(wLines[idx], "NettoVDR", max_width=maxTextWidth, max_font_size=maxFontSize)    # get appropriate fontsize to fit the longest line
    
    c.setFont("NettoVDR", fontSize)   
    
    for line in wLines[:-1]:
        c.drawCentredString(x, yText, line)
        yText -= fontSize
    
    c.setFont("NettoBold", fontSize)
    c.drawCentredString(x, yText, wLines[-1])           # draw equipment or meeting room info in bold.
    

def split_string_at_middle(text: str) -> list[str]:
    lhalf, rhalf = text[:len(text) // 2], text[(len(text) // 2):]
    
    if lhalf[-1] == " " or rhalf[0] == " ": 
        return [lhalf, rhalf]
    else:
        return [lhalf + "-", rhalf]


def updateProgressBar(index: int, entries: pd.DataFrame, url: str, progressBar: ProgressBarState):
    value = round(100 * cast(int, index) / entries.shape[0])
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