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


QR_CODE_CAPTION = "Scannez le QR code avec votre télphone HRC afin de signaler un problème."
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


def genLargeVerticalQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState): 
    progressBar.progressBar.setValue(0)
    
    print("genLargeVerticalQRPDFsFor")
    QRCodeSize = 100 * mm
    width, height = A4
    fontSize, charsPerLine = 16, 40
    
    xStart, yStart = 15 * mm, height - 35 * mm
    x, y = xStart, yStart
    
    outputPath = "./output/largeVerticalQRs.pdf"
    
    c = canvas.Canvas(outputPath, pagesize=A4)
    pdfmetrics.registerFont(TTFont('NettoVDR', './assets/Netto-Regular.ttf'))
    c.setFont("NettoVDR", fontSize)
    
    count = 0
    
    for index, (_, row) in enumerate(entries.iterrows()):
        
        c.drawImage("./assets/hrc-logo.jpg", x, y, width=1.25*HRC_LOGO_WIDTH, height=1.25*HRC_LOGO_HEIGHT)
        
        y -= QRCodeSize
        x -= 12 * mm
        
        url = getUrlFrom(row)
        value = round(100 * cast(int, index) / entries.shape[0])
        print(value)
        
        progressBar.label.setText(url)
        progressBar.progressBar.setValue(value)
        
        QCoreApplication.processEvents()                # keep ui responsive by processing events
        
        c.drawImage(getQRImageReaderFromRow(url), x, y, width=QRCodeSize, height=QRCodeSize)                    # draw the QR code
        
        c.setFont("NettoVDR", fontSize)
        
        wLines: list[str] = textwrap.wrap(QR_CODE_CAPTION, width=charsPerLine)               # "wrap" caption to array of strings of max chars per entry.
        yText = y
        for line in wLines:
            c.drawCentredString(x + QRCodeSize / 2, yText, line)
            yText -= fontSize
        
        if is_eq_csv:
            c.drawCentredString(x + QRCodeSize / 2, yText, f"{row["Modèle"]} {row["Code matériel"]}")
        else:
            c.drawCentredString(x + QRCodeSize / 2, yText, f"Salle de Réunion {row["Numéro de Signalétique"]} {row["Localisation"]}")
            
        count += 1
        
        if count % 4 == 0:
            c.showPage()
            x, y = xStart, yStart
            count = 0
        else:
            # manually hardcore all QR code positions (coded to fit to a 3483 sticker sheet)
            if count == 1:
                x, y = 119 * mm, height - 35 * mm
            elif count == 2:
                x, y = 15 * mm, height - 182 * mm
            elif count == 3:
                x, y = 119 * mm, height - 182 * mm
    
    progressBar.progressBar.setValue(100)
    c.save()
    print(f"LOG: PDF saved as: {outputPath}")


def genMediumHorizontalQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState): # entries (code, model, image)
    progressBar.progressBar.setValue(0)
    
    print("genMediumHorizontalQRPDFsFor")
    QRCodeSize = 44 * mm
    width, height = A4
    fontSize, charsPerLine = 12, 30
    xStart, yStart = 3 * mm, height - 28 * mm
    x, y = xStart, yStart
    
    outputPath = "./output/mediumHorizontalQRs.pdf"
    
    c = canvas.Canvas(outputPath, pagesize=A4)
    pdfmetrics.registerFont(TTFont('NettoVDR', './assets/Netto-Regular.ttf'))
    c.setFont("NettoVDR", fontSize)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        c.drawImage("./assets/hrc-logo.jpg", x, y, width=0.9*HRC_LOGO_WIDTH, height=0.9*HRC_LOGO_HEIGHT)
        c.setFont("NettoVDR", fontSize)
        
        wLines: list[str] = textwrap.wrap(QR_CODE_CAPTION, width=charsPerLine)               # "wrap" caption to array of strings of max chars per entry.
        yText = y - fontSize
        
        for line in wLines:
            c.drawCentredString(x + 27*mm, yText, line)
            yText -= fontSize
            
        if is_eq_csv:
            c.drawCentredString(x + QRCodeSize / 2, yText, f"{row["Modèle"]} {row["Code matériel"]}")
        else:
            c.drawCentredString(x + QRCodeSize / 2, yText, f"Salle de Réunion {row["Numéro de Signalétique"]} {row["Localisation"]}")
        
        x += 55*mm                  # move cursor bottom right of text to draw QR code
        y = yText - 5*mm
        
        url = getUrlFrom(row)
        value = round(100 * cast(int, index) / entries.shape[0])
        print(value)
        
        progressBar.label.setText(url)
        progressBar.progressBar.setValue(value)
        
        QCoreApplication.processEvents()                # keep ui responsive by processing events
        
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


def genSmallSquareQRPDFsFor(is_eq_csv: bool, entries: pd.DataFrame, progressBar: ProgressBarState):
    progressBar.progressBar.setValue(0)
    
    print("genSmallSquareQRPDFsFor")
    QRCodeSize = 60 * mm
    width, height = A4
    fontSize, charsPerLine = 9, 36
    xStart, yStart = 2.5 * mm, height - 13 * mm - 58 * mm                                       # top-margin minus 5 height of sticker square (Zweckform 3661)
    x, y = xStart, yStart
    
    outputPath = "./output/smallSquarePDFs.pdf"
    
    c = canvas.Canvas(outputPath, pagesize=A4)
    pdfmetrics.registerFont(TTFont('NettoVDR', './assets/Netto-Regular.ttf'))
    c.setFont("NettoVDR", fontSize)
    
    count = 0
    for index, (_, row) in enumerate(entries.iterrows()):
        url = getUrlFrom(row)
        value = round(100 * cast(int, index) / entries.shape[0])
        print(value)
        
        progressBar.label.setText(url)
        progressBar.progressBar.setValue(value)
        
        QCoreApplication.processEvents()                # keep ui responsive by processing events
        
        
        c.drawImage(getQRImageReaderFromRow(url, True), x, y, width=QRCodeSize, height=QRCodeSize)
        c.setFont("NettoVDR", fontSize)
        
        wLines: list[str] = textwrap.wrap(QR_CODE_CAPTION, width=charsPerLine)               # "wrap" caption to array of strings of max chars per entry
        yText = y
        
        for line in wLines:
            c.drawCentredString(x + 30*mm, yText, line)
            yText -= fontSize
        
        if is_eq_csv:
            c.drawCentredString(x + 30*mm, yText, f"{row["Modèle"]} {row["Code matériel"]}")
        else:
            c.drawCentredString(x + 30*mm, yText, f"Salle de Réunion {row["Numéro de Signalétique"]} {row["Localisation"]}")
        
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
