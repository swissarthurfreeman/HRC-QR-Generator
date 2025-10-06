import sys
from pprint import pprint
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLabel, QComboBox, QFileDialog, QWidget, QScrollArea, QPushButton, QHBoxLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from pdf import genLargeVerticalQRPDFsFor, genMediumHorizontalQRPDFsFor, genSmallSquareQRPDFsFor

# TODO : refactor this to a configuration object class. 
def reset() -> dict:
    return {
    "Grand Vertical (largeur, hauteur) = (10.4 cm, 14.7 cm)": { 
        'models': [],
        'rows': pd.DataFrame(), 
        'func': genLargeVerticalQRPDFsFor 
    },
    "Moyen Horizontal (largeur, hauteur) = (10.4 cm, 4.8 cm)": { 
        'models': [], 
        'rows': pd.DataFrame(), 
        'func': genMediumHorizontalQRPDFsFor
    },
    "Petit Carré (largeur, hauteur) = (6.9 cm, 6.7 cm)": { 
        'models': [], 
        'rows': pd.DataFrame(), 
        'func': genSmallSquareQRPDFsFor
    }
} 

# Hardcoded QR code formats and their respective models list and generation function.
QR_CODE_FORMATS = reset()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Générateur de QR codes de matériel EasyVista")
        self.setGeometry(100, 100, 1000, 600)

        # superclass of all visual Qt elements (button, dropdown, labels...)
        # allows placing other widgets, handling clicks, dropdowns etc. 
        self.central_widget: QWidget = QWidget()                 
        self.setCentralWidget(self.central_widget)      # parent widget of the app
        # https://doc.qt.io/qt-6/qvboxlayout.html#details
        self.layout: QVBoxLayout = QVBoxLayout(self.central_widget)  # used to construct vertical box layout objects

        # Drag-and-drop area, configure a label for that https://doc.qt.io/qt-6/qlabel.html
        self.drop_label = QLabel("Glisser et déposer un fichier CSV ici ou clickez afin d'en séléctionner un.")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("border: 2px dashed #aaa; padding: 20px;")    # dashed line frame
        #self.drop_label.setAcceptDrops(True)                                       # not needed since we set this on parent.                                        
        self.drop_label.mousePressEvent = self.open_file_dialog
        self.layout.addWidget(self.drop_label)      # add the label to the Vertifcal Layout (csv dropdown label | list of models title | list of dropdown selects)

        # Scrollable area for model list https://doc.qt.io/qt-6/qscrollarea.html#details
        # A scroll area is used to display the contents of a child widget within a frame. 
        # If the widget exceeds the size of the frame, the view can provide scroll bars so 
        # that the entire area of the child widget can be viewed. The child widget must be 
        # specified with setWidget().
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)       # will contain the model, dropdowns, close triples.
        self.scroll_area.setWidget(self.scroll_content)             # scroll area contains the scroll content (list of dropdowns) 
        self.layout.addWidget(self.scroll_area)                     

        # Enable drag-and-drop functionality https://doc.qt.io/qt-6/qwidget.html#acceptDrops-prop
        # allows registering a dropEvent() hook
        self.setAcceptDrops(True)
        
        # either columns with information about EZV equipments or meeting rooms.
        self.eq_mand_cols = ["Modèle", "Code matériel", "Catégorie", "Numéro de Série"]
        self.room_mand_cols =  ["Numéro de Signalétique", "Localisation"]
        
    def open_file_dialog(self, event=None):
        file_path, _ = QFileDialog.getOpenFileName(self, "Séléctionner le CSV d'inventaire EasyVista", "", "CSV Files (*.csv)")
        if file_path:
            self.process_csv(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():                  # TODO : review this code, seems redundant with dropEvent
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handler for drop events, fired when a file is dropped into the window."""
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.endswith(".csv"):
                if self.process_csv(file_path) == 0: # i.e. processed without errors
                    # configure generation button.
                    self.generate_button = QPushButton("Générer!")
                    self.generate_button.setFixedWidth(100)
                    self.generate_button.clicked.connect(self.on_generate_clicked)
                    self.layout.addWidget(self.generate_button)
                
                    # configure progress bar.
                    self.progress = QProgressBar(self)
                    self.progress.setRange(0, 100)  # from 0% to 100%
                    self.layout.addWidget(self.progress)
                    self.timer = QTimer()
                    self.timer.timeout.connect(self.handle_timer)
                    self.value = 0
                
            else:
                self.drop_label.setText("Merci de fournir un fichier CSV valide.")
        else:
            event.ignore()

    def on_generate_clicked(self, _):
        QR_CODE_FORMATS = reset()
    
        if self.is_eq_csv:                                          # if we're dealing with equipments list (no model column)
            for i in range(1, self.scroll_layout.count()):
                qr_format = self.scroll_layout.itemAt(i).itemAt(3).widget().currentText() 
                model = self.scroll_layout.itemAt(i).itemAt(1).widget().text()
                QR_CODE_FORMATS[qr_format]['models'].append(model)
                
            for qr_format in QR_CODE_FORMATS:
                QR_CODE_FORMATS[qr_format]['rows'] = self.csv_df[self.csv_df['Modèle'].isin(QR_CODE_FORMATS[qr_format]['models'])][self.eq_mand_cols].sort_values("Modèle")
        
            for qr_format in QR_CODE_FORMATS.keys():
                QR_CODE_FORMATS[qr_format]['func'](self.is_eq_csv, QR_CODE_FORMATS[qr_format]['rows'])      # call generate QR codes for equipment.
                
        else:
            # retrive the selected qr format for meeting rooms csv (only one model)
            qr_format = self.scroll_layout.itemAt(1).itemAt(3).widget().currentText()
            QR_CODE_FORMATS[qr_format]['rows'] = self.csv_df[self.room_mand_cols]
            QR_CODE_FORMATS[qr_format]['func'](self.is_eq_csv, QR_CODE_FORMATS[qr_format]['rows'])          # call generate QR codes for meeting rooms.
    
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

    def process_csv(self, file_path) -> int:
        """Read CSV file at @param file_path, check Modèle and Code Matériel column is provided.
        If 'Numéro de Série' is provided, it'll be used in the encoded URLs, but it's not mandatory. 
        """
        try:
            # Read CSV and check present columns
            self.csv_df: pd.DataFrame = pd.read_csv(file_path, sep=";", index_col=False)
            csv_cols = set(self.csv_df.columns.to_list()) 
            
            
            self.is_eq_csv = set(self.eq_mand_cols).issubset(csv_cols)
            is_room_csv = set(self.room_mand_cols).issubset(csv_cols)
            
            if not (self.is_eq_csv or is_room_csv):
                self.drop_label.setText(f"Format de CSV non valide. Fournissez soit {self.eq_mand_cols} pour des équipements, soit {self.room_mand_cols} pour des salles de réunion.")
                return 1
            
            mand_cols = self.eq_mand_cols if self.is_eq_csv else self.room_mand_cols
            for mand_col in mand_cols:
                if self.col_contains_blanks(self.csv_df[mand_col]):
                    self.drop_label.setText(f"Format de CSV non valide. Colonne '{mand_col}' contient des valeurs vides.")
                    return 1
                
            # retrieve list of equipment models.
            unique_models: list[str] = self.csv_df["Modèle"].dropna().unique().tolist() if self.is_eq_csv else ["Salle de Réunion"]
            unique_models.sort()
            
            if len(unique_models) == 0: 
                self.drop_label.setText("Aucun équipement présent dans le fichier.")
                return 1
            
            # Add title
            title_label = QLabel("Veuillez Choisir le format de QR code par Modèle d'Équipement" if self.is_eq_csv else "Choissisez le format de QR code")
            title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)  # Align inside the label
            title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
            self.scroll_layout.addWidget(title_label)

            # avoids spacing issues when removing models
            self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            # Add models with dropdowns and remove buttons
            for model in unique_models:
                model_layout = QHBoxLayout()  # Use horizontal layout for dropdown and button
                #model_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                model_label = QLabel(model.strip())
                
                # if it's an equipments csv, count number of instances per model, otherwise, it's a meeting room csv, only one type, with number of lines instances.
                count_label = QLabel("(" + str(self.csv_df["Modèle"].value_counts()[model] if self.is_eq_csv else self.csv_df.count().iloc[0]) + " instances)")
                # A QComboBox is a compact way to present a list of options to the user. A combobox is 
                # a selection widget that shows the current item, and pops up a list of selectable items 
                # when clicked. Comboboxes can contain pixmaps as well as strings if the insertItem() 
                # and setItemText() functions are suitably overloaded.
                dropdown = QComboBox()
                dropdown.setFixedWidth(350)
                dropdown.addItems(list(QR_CODE_FORMATS.keys()))      # list of descriptive strings.

                remove_button = QPushButton("X")
                remove_button.setFixedWidth(30)  # Set width for the button
                remove_button.clicked.connect(lambda _, m=model, l=model_layout: self.remove_model(m, l))

                model_layout.addWidget(remove_button)
                model_layout.addWidget(model_label)
                model_layout.addWidget(count_label)
                model_layout.addWidget(dropdown)
                self.scroll_layout.addLayout(model_layout)
                
            self.drop_label.setVisible(False)
            self.setAcceptDrops(False)
            
            return 0

        except Exception as e:
            self.drop_label.setText(f"Error processing file: {str(e)}")
            return 0

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
