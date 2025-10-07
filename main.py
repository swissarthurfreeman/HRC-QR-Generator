import sys
import pandas as pd
from collections.abc import Callable
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLabel, QComboBox, QFileDialog, QWidget, QScrollArea, QPushButton, QHBoxLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from pdf import genLargeVerticalQRPDFsFor, genMediumHorizontalQRPDFsFor, genSmallSquareQRPDFsFor


class QRCodeFormat:
    def __init__(self, description, func: Callable[[bool, pd.DataFrame], None]):
        self.description = description
        self.generatePDFsFunc: Callable[[bool, pd.DataFrame], None] = func
        self.models: list[str] = []                     # used to filter rows from CSV.

class GenerationConfig:
    def __init__(self, qrFormats: list[QRCodeFormat]):
        self.formats: dict[str, QRCodeFormat] = {}      # mapping from format description string to QRCodeFormat.
        for qrFormat in qrFormats:
            self.formats[qrFormat.description] = qrFormat
    
    @staticmethod
    def default():
        return GenerationConfig([       # Hardcoded QR code formats and their respective generation function, add new formats here.
            QRCodeFormat("Grand Vertical (largeur, hauteur) = (10.4 cm, 14.7 cm)", genLargeVerticalQRPDFsFor),
            QRCodeFormat("Moyen Horizontal (largeur, hauteur) = (10.4 cm, 4.8 cm)", genMediumHorizontalQRPDFsFor),
            QRCodeFormat("Petit Carré (largeur, hauteur) = (6.9 cm, 6.7 cm)", genSmallSquareQRPDFsFor)
        ])
    
    def getFormatsStrings(self) -> list[str]:
        return list(self.formats.keys())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.generationConfig: GenerationConfig = GenerationConfig.default()          # configuration of PDF generation, contains PDF function, qr code format and rows associations.
        
        self.setWindowTitle("Générateur de QR codes de matériel EasyVista")
        self.setGeometry(100, 100, 1000, 600)

        self.central_widget: QWidget = QWidget()                     # superclass of Qt elements (button, dropdown, labels...) allows placing, handle clicks, dropdowns etc.                  
        self.setCentralWidget(self.central_widget)                   # parent widget of the app
        self.layout: QVBoxLayout = QVBoxLayout(self.central_widget)  # https://doc.qt.io/qt-6/qvboxlayout.html#details, construct vertical box layout objects

        
        self.drop_label = QLabel("Glisser et déposer un fichier CSV ici ou clickez afin d'en séléctionner un.") 
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)                  # Drag-and-drop area, just a dashed line framed label https://doc.qt.io/qt-6/qlabel.html
        self.drop_label.setStyleSheet("border: 2px dashed #aaa; padding: 20px;")    
        self.drop_label.mousePressEvent = self.open_file_dialog # type: ignore
        self.layout.addWidget(self.drop_label)                                      # add the label to the Vertifcal Layout (drag and drop field | list of models title | list of dropdown selects)

        self.scroll_area = QScrollArea()                            # model list Scrollable area, displays contents of child widget in frame https://doc.qt.io/qt-6/qscrollarea.html#details
        self.scroll_area.setWidgetResizable(True)                   # if widget exceeds size of frame, view provides scroll bars.
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)       # will contain the model, dropdowns, close triples.
        self.scroll_area.setWidget(self.scroll_content)             # child widget (that needs scrollbars) is specified here. Scroll area contains the list of dropdowns 
        self.layout.addWidget(self.scroll_area)                     

        self.setAcceptDrops(True)   # Enable drag-and-drop on whole window, requires registering dropEvent() hook https://doc.qt.io/qt-6/qwidget.html#acceptDrops-prop
                
        self.eq_mand_cols = ["Modèle", "Code matériel", "Catégorie", "Numéro de Série"]     # mandatory columns or schema of CSV
        self.room_mand_cols =  ["Numéro de Signalétique", "Localisation"]                   # either columns with information about EZV equipments or meeting rooms.
        
    def open_file_dialog(self, event=None):
        file_path, _ = QFileDialog.getOpenFileName(self, "Séléctionner le CSV d'inventaire EasyVista", "", "CSV Files (*.csv)")
        if file_path:
            self.process_csv(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Fired when a file is dragged over the screen. If it's a CSV file we accept it can be dropped, otherwise ignore."""
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].toLocalFile().endswith(".csv"):    # type: ignore urls is an array [file://PATH_TO_DROPPED_FILE] of size 1.
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Fired when a file is dropped into the window, file is checked if .csv in @dragEnterEvent"""
        file_path = event.mimeData().urls()[0].toLocalFile()
        
        try: 
            self.process_csv(file_path)                             # will throw if provided file isn't valid.
            self.addGenerateButtonAndLoadingBar()               
        except Exception as err:
            self.drop_label.setText(f"Erreur : {str(err)}")
        
    def addGenerateButtonAndLoadingBar(self):
        self.generate_button = QPushButton("Générer!")              # configure generation button.
        self.generate_button.setFixedWidth(100)
        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.layout.addWidget(self.generate_button)
    
        self.progress = QProgressBar(self)                          # configure progress bar.        
        self.progress.setRange(0, 100)  # from 0% to 100%
        self.layout.addWidget(self.progress)
        self.timer = QTimer()
        self.timer.timeout.connect(self.handle_timer)
        self.value = 0
        
    def read_and_validate_csv(self, file_path):
        """Read and validate CSV file. Expects a non empty utf-8 file containing either `eq_mand_cols` or `room_mand_cols` defined 
        in the constructor. Equipments: `Numéro de Série, Code matériel, Modèle, Catégorie`, Meeting rooms: `Numéro de 
        Signalétique, Localisation`"""
        try:    # read and validate it is a CSV
            self.csv_df: pd.DataFrame = pd.read_csv(file_path, sep=";", index_col=False)
        except Exception as e:
            self.drop_label.setText(f"Error processing file: {str(e)}")
            return 0
        
        columns = set(self.csv_df.columns.to_list())                    # check presence of columns
        self.is_eq_csv = set(self.eq_mand_cols).issubset(columns)
        
        if not (self.is_eq_csv or set(self.room_mand_cols).issubset(columns)):  # if it's not an equipment csv or we don't have all columns for a room csv
            raise Exception(f"Format de CSV non valide. Fournissez soit {self.eq_mand_cols} pour des équipements, soit {self.room_mand_cols} pour des salles de réunion.")
        
        mand_cols = self.eq_mand_cols if self.is_eq_csv else self.room_mand_cols
        for mand_col in mand_cols:
            if self.col_contains_blanks(self.csv_df[mand_col]):
                raise Exception(f"Format de CSV non valide. Colonne '{mand_col}' contient des valeurs vides.")
        
        if self.csv_df.shape[0] == 0: 
            raise Exception("Aucun équipement présent dans le fichier.")
            
    def process_csv(self, file_path):
        """Read CSV file at @param file_path, check Modèle and Code Matériel column is provided.
        If 'Numéro de Série' is provided, it'll be used in the encoded URLs, but it's not mandatory.
        Will throw an exception if error is encountered. 
        """
        self.read_and_validate_csv(file_path)
        
        self.unique_models: list[str] = self.csv_df["Modèle"].dropna().unique().tolist() if self.is_eq_csv else ["Salle de Réunion"]  # retrieve list of equipment models.
        self.unique_models.sort()
        
        if self.is_eq_csv:
            self.csv_df = self.csv_df[self.eq_mand_cols].sort_values("Modèle")    # keep only mandatory columns, sort by model.
        else: 
            self.csv_df = self.csv_df[self.room_mand_cols]                        # keep only mandatory columns for meeting rooms.
        
        self.populate_model_list()
    
    def populate_model_list(self):
        title_label = QLabel("Veuillez Choisir le format de QR code par Modèle d'Équipement" if self.is_eq_csv else "Choissisez le format de QR code")
        title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)  # Align inside the label
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.scroll_layout.addWidget(title_label)

        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)          # avoids spacing issues when removing models

        # Add models with dropdowns and remove buttons
        for model in self.unique_models:
            model_layout = QHBoxLayout()                        # horizontal layout for dropdown, buttons and labels.
            model_label = QLabel(model.strip())
            
            # if it's an equipments csv, count number of instances per model, else if meeting room csv, it's just N°lines.
            count_label = QLabel("(" + str(self.csv_df["Modèle"].value_counts()[model] 
                                           if self.is_eq_csv else self.csv_df.shape[0]) + " instances)")
            
            dropdown = QComboBox()                               # presents a list of options to the user, selection widget. 
            dropdown.setFixedWidth(350)
            dropdown.addItems(self.generationConfig.getFormatsStrings())      # list of descriptive strings.

            remove_button = QPushButton("X")
            remove_button.setFixedWidth(30)
            remove_button.clicked.connect(lambda _, m=model, l=model_layout: self.remove_model(m, l))

            model_layout.addWidget(remove_button)
            model_layout.addWidget(model_label)
            model_layout.addWidget(count_label)
            model_layout.addWidget(dropdown)
            self.scroll_layout.addLayout(model_layout)
            
        self.drop_label.setVisible(False)
        self.setAcceptDrops(False)

    def on_generate_clicked(self, _):
        """Read the dropdown values, associate models to QR code formats, call the PDF generation functions."""
        self.generationConfig: GenerationConfig = GenerationConfig.default()            # reset config back to default
        
        if self.is_eq_csv:                                          # if we're dealing with equipments list (no model column)
            for i in range(1, self.scroll_layout.count()):
                qrFormat = self.scroll_layout.itemAt(i).itemAt(3).widget().currentText()    # type: ignore
                model = self.scroll_layout.itemAt(i).itemAt(1).widget().text()              # type: ignore
                
                self.generationConfig.formats[qrFormat].models.append(model)
                
            for qrFormat in self.generationConfig.formats:                      # filter to only rows matching the selected models for this format and generate PDFs
                rowsOfModel = self.csv_df[self.csv_df['Modèle'].isin(self.generationConfig.formats[qrFormat].models)]
                self.generationConfig.formats[qrFormat].generatePDFsFunc(self.is_eq_csv, rowsOfModel)
                
        else:
            qrFormat = self.scroll_layout.itemAt(1).itemAt(3).widget().currentText()                # type: ignore retrive the selected qr format for meeting rooms csv (only one model)
            self.generationConfig.formats[qrFormat].generatePDFsFunc(self.is_eq_csv, self.csv_df)   # call generate QR codes for meeting rooms.
                    
    
    def start_loading(self):            # TODO : cleanup and merge with pdf writing logic. 
        self.value = 0
        self.progress.setValue(self.value)
        self.timer.start(50)  # update every 50ms

    def handle_timer(self):
        if self.value >= 100:
            self.timer.stop()
        else:
            self.value += 1
            self.progress.setValue(self.value)

    def col_contains_blanks(self, col: pd.Series) -> bool:
        return col.isna().any() or col.astype(str).str.strip().eq("").any()

    
    def remove_model(self, model, layout):
        """Remove a specific model from the list."""
        for i in reversed(range(layout.count())):           # TODO : understand this code
            layout.itemAt(i).widget().deleteLater()
        self.scroll_layout.removeItem(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
