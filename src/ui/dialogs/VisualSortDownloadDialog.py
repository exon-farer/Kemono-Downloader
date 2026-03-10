import os
import requests
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar, 
                             QPushButton, QMessageBox, QRadioButton, QButtonGroup, 
                             QHBoxLayout, QGroupBox, QTabWidget, QWidget, QSlider, 
                             QSpinBox, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings

class DownloadWorker(QThread):
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, models_dir, model_path, csv_path, model_url, csv_url):
        super().__init__()
        self.models_dir = models_dir
        self.model_path = model_path
        self.csv_path = csv_path
        self.model_url = model_url
        self.csv_url = csv_url

    def run(self):
        try:
            os.makedirs(self.models_dir, exist_ok=True)
            files = [
                (self.model_url, self.model_path, "Downloading AI model..."),
                (self.csv_url, self.csv_path, "Downloading tag database...")
            ]
            
            for url, path, label in files:
                self.status_signal.emit(label)
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                total = int(response.headers.get('content-length', 0))
                
                downloaded = 0
                with open(path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.isInterruptionRequested():
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.progress_signal.emit(int(downloaded / total * 100))
                
            self.status_signal.emit("Initializing AI engine...")
            
            # Using absolute import relative to where this script is meant to run
            # Adjusted based on typical project structure (from...core)
            try:
                from src.core.visual_sorter import VisualSorter
            except ImportError:
                # Fallback if standard structure isn't present
                from .visual_sorter import VisualSorter
                
            VisualSorter.get_instance(self.model_path, self.csv_path)
            
            self.finished_signal.emit(True, "Success")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class VisualSortSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visual Sort Setup")
        self.setObjectName("VisualSortSetupDialog") # For styling targeting
        
        self.setMinimumSize(500, 400)
        self.resize(550, 480) # Increased height slightly for the new tab look
        self.setWindowModality(Qt.WindowModal)
        
        self.settings = QSettings("MediaDownloader", "VisualSort")

        # Main Layout with proper margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SetupTabs") # Required for the stylesheet targeting
        main_layout.addWidget(self.tabs)
        
        # Setup Tabs
        self.setup_download_tab()
        self.setup_settings_tab()
        
        # Native Dialog Button Box
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        self.button_box.accepted.connect(self.apply_and_close)
        self.button_box.rejected.connect(self.close)
        main_layout.addWidget(self.button_box)

        # Apply the styling (defined at the bottom)
        self.set_custom_styles()

        # File Paths
        self.models_dir = os.path.abspath(os.path.join("appdata", "models"))
        self.model_path = os.path.join(self.models_dir, "model.onnx")
        self.csv_path = os.path.join(self.models_dir, "selected_tags.csv")

        self.worker = None

        self.model_urls = {
            0: {
                "model": "https://huggingface.co/SmilingWolf/wd-vit-tagger-v3/resolve/main/model.onnx",
                "csv": "https://huggingface.co/SmilingWolf/wd-vit-tagger-v3/resolve/main/selected_tags.csv"
            },
            1: {
                "model": "https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3/resolve/main/model.onnx",
                "csv": "https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3/resolve/main/selected_tags.csv"
            },
            2: {
                "model": "https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3/resolve/main/model.onnx",
                "csv": "https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3/resolve/main/selected_tags.csv"
            }
        }

    def setup_download_tab(self):
        tab = QWidget()
        tab.setObjectName("DownloadTab")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        explanation = QLabel("Visual Sort requires an AI model to classify characters.\nPlease select the model you wish to install:")
        explanation.setWordWrap(True)
        explanation.setStyleSheet("font-size: 13px; margin-bottom: 5px;")
        layout.addWidget(explanation)

        self.group_box = QGroupBox("Model Selection")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(15, 20, 15, 15)

        self.radio_group = QButtonGroup(self)
        
        self.rb_basic = QRadioButton("Basic - Fast (~379MB)")
        self.rb_basic.setToolTip("Recommended for quick sorting.\nDownloads faster and uses less system memory.")
        
        self.rb_balanced = QRadioButton("Balanced - Recommended (~440MB)")
        self.rb_balanced.setToolTip("A great middle-ground.\nOffers better accuracy for character recognition.")
        
        self.rb_advanced = QRadioButton("Advanced - Best Accuracy (~1.26GB)")
        self.rb_advanced.setToolTip("The largest model.\nSlowest to download and process, but yields the highest recognition quality.")
        
        self.radio_group.addButton(self.rb_basic, 0)
        self.radio_group.addButton(self.rb_balanced, 1)
        self.radio_group.addButton(self.rb_advanced, 2)
        
        self.rb_balanced.setChecked(True)
        
        group_layout.addWidget(self.rb_basic)
        group_layout.addWidget(self.rb_balanced)
        group_layout.addWidget(self.rb_advanced)
        self.group_box.setLayout(group_layout)
        
        layout.addWidget(self.group_box)

        self.status_label = QLabel("Ready to download.")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()

        self.download_btn = QPushButton("Download Selected Model")
        self.download_btn.setMinimumHeight(35) 
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        self.tabs.addTab(tab, "Download")

    def setup_settings_tab(self):
        tab = QWidget()
        tab.setObjectName("SettingsTab")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        settings_group = QGroupBox("Sorting Configuration")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(15)
        settings_layout.setContentsMargins(15, 20, 15, 15)

        threshold_label = QLabel("Character Detection Threshold (%)")
        settings_layout.addWidget(threshold_label)

        slider_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(1, 100)
        
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setSuffix("%")
        self.threshold_spin.setMinimumWidth(70)

        saved_threshold = self.settings.value("char_threshold", 50, type=int)
        self.threshold_slider.setValue(saved_threshold)
        self.threshold_spin.setValue(saved_threshold)

        self.threshold_slider.valueChanged.connect(self.threshold_spin.setValue)
        self.threshold_spin.valueChanged.connect(self.threshold_slider.setValue)

        slider_layout.addWidget(self.threshold_slider)
        slider_layout.addWidget(self.threshold_spin)
        settings_layout.addLayout(slider_layout)

        desc_label = QLabel("Lower values detect more characters but may increase mistakes.\nHigher values are stricter but may send more images to the Unknown folder.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888; font-style: italic; margin-top: 5px;")
        settings_layout.addWidget(desc_label)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        layout.addStretch()

        self.tabs.addTab(tab, "Settings")

    def apply_and_close(self):
        # Save the threshold only when OK is clicked
        self.settings.setValue("char_threshold", self.threshold_spin.value())
        self.accept()

    def start_download(self):
        self.group_box.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        
        selected_id = self.radio_group.checkedId()
        urls = self.model_urls[selected_id]
        
        self.worker = DownloadWorker(
            self.models_dir, 
            self.model_path, 
            self.csv_path,
            urls["model"],
            urls["csv"]
        )
        self.worker.status_signal.connect(self.status_label.setText)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, success, error_msg):
        self.group_box.setEnabled(True)
        self.download_btn.setEnabled(True)
        if success:
            self.progress_bar.hide()
            self.status_label.setText("Model installed successfully.")
            QMessageBox.information(self, "Download Complete", "The AI model is ready to use.")
        else:
            QMessageBox.critical(self, "Download Error", f"Failed to setup Visual Sort:\n{error_msg}")
            self.progress_bar.hide()
            self.progress_bar.setValue(0)
            self.status_label.setText("Download failed. Try again.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        super().closeEvent(event)

    def set_custom_styles(self):
        # Uses the exact same tab styling found in FutureSettingsDialog.py
        # to ensure visual consistency across the application.
        
        qss = """
            /* Main Dialog and Tab backgrounds */
            #VisualSortSetupDialog, #DownloadTab, #SettingsTab {
                background-color: #2D2D2D;
            }

            /* Tab Widget Pane */
            QTabWidget::pane {
                border-top: 1px solid #444;
                margin-top: -1px; /* Overlap with tab bar */
                background-color: #2D2D2D;
            }

            /* Inactive Tabs */
            QTabBar::tab {
                background-color: #3D3D3D;
                color: #BBBBBB;
                border: 1px solid #444;
                border-bottom: none; /* No bottom border for tabs */
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }

            /* Selected/Active Tab */
            QTabBar::tab:selected {
                background-color: #2D2D2D; /* Same as pane background */
                color: #EEEEEE;
                border-bottom: 1px solid #2D2D2D; /* Hides the pane top border */
                margin-bottom: -1px; /* Pulls tab down to cover pane border */
            }

            /* Hover state for inactive tabs */
            QTabBar::tab:!selected:hover {
                background-color: #4A4A4A;
            }
            
            /* Basic text colors to ensure readability on the dark background */
            QLabel, QRadioButton, QCheckBox, QGroupBox {
                color: #EEEEEE;
            }
            
            /* GroupBox border styling for consistency */
            QGroupBox {
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """
        self.setStyleSheet(qss)