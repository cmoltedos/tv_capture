import sys, os
import platform
import datetime, time
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from pdb import set_trace

import stream_capture as streamer

class DownloadStreamProgress(QtCore.QThread):
    percentChanged = QtCore.pyqtSignal(int)

    def __init__(self, stream):
        super(DownloadStreamProgress, self).__init__()
        self.stream = stream

    def run(self):
        self._isRunning = True
        for percent in self.stream:
            if not self._isRunning:
                break
            self.percentChanged.emit(percent)

    def stop(self):
        self._isRunning = False


class ProgramStreamWidget(QtWidgets.QVBoxLayout):

    def __init__(self, folder, status_bar):
        super(ProgramStreamWidget, self).__init__()
        self.stream = None
        self.quality = None
        self.working_folder = folder
        self.status_bar = status_bar

    def create_tab_program_layout(self):
        group = QtWidgets.QGroupBox("Chapter to download URL:")
        layout = QtWidgets.QFormLayout()
        self.program_url = QtWidgets.QTextEdit()
        self.program_url.textChanged.connect(self.set_program_quality)
        layout.addRow(self.program_url)
        quality_label = QtWidgets.QLabel('Video quality:')
        self.program_quality = QtWidgets.QComboBox()
        self.program_quality.currentTextChanged.connect(self.set_quality)
        layout.addRow(quality_label, self.program_quality)
        group.setLayout(layout)
        self.addWidget(group)

        grid = QtWidgets.QGridLayout()
        self.program_start_download_button = QtWidgets.QPushButton(
            'Start Download')
        self.program_start_download_button.setEnabled(False)
        self.program_start_download_button.clicked.connect(
            self.start_stream_download)
        grid.addWidget(self.program_start_download_button, 1, 1)
        self.program_stop_download_button = QtWidgets.QPushButton(
            'Stop Download')
        self.program_stop_download_button.setEnabled(False)
        self.program_stop_download_button.clicked.connect(
            self.finish_stream_download)
        grid.addWidget(self.program_stop_download_button, 1, 2)
        self.addLayout(grid)

        self.pbar = QtWidgets.QProgressBar()
        self.pbar.setGeometry(30, 40, 200, 10)
        self.addWidget(self.pbar)

        return "Program Downloader"

    def set_quality(self):
        quality = self.program_quality.currentText()
        self.quality = quality

    def set_program_quality(self):
        link = self.program_url.toPlainText()
        try:
            self.stream = streamer.Stream(link=link)
        except IOError:
            self.program_start_download_button.setEnabled(False)
            return None
        qualities = self.stream.get_available_resolution()
        self.program_quality.clear()
        self.program_quality.addItems(qualities)
        self.program_start_download_button.setEnabled(True)

    def start_stream_download(self):
        self.program_start_download_button.setEnabled(False)
        self.program_stop_download_button.setEnabled(True)
        progress = self.stream.store_n_seconds(
            seconds=1, resolution=self.quality,
            folder=self.working_folder.text()
        )
        self.progress = DownloadStreamProgress(progress)
        self.progress.percentChanged.connect(self.onpercentChanged)
        self.status_bar.showMessage('Downloading ...')
        self.progress.start()

    def finish_stream_download(self):
        self.progress.stop()
        self.program_start_download_button.setEnabled(True)
        self.program_stop_download_button.setEnabled(False)
        self.pbar.setValue(0)
        self.status_bar.showMessage('Finish')

    def onpercentChanged(self, value):
        if value >= 100:
            self.pbar.setValue(100)
            self.finish_stream_download()
        else:
            self.pbar.setValue(value)


class MyTableWidget(QtWidgets.QWidget):

    def __init__(self, parent):
        super(MyTableWidget, self).__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()

        # Common working folder
        group = QtWidgets.QGroupBox("Working folder:")
        folder_layout = QtWidgets.QFormLayout()
        self.set_folder_edit()
        folder_selector = self.set_folder_button()
        folder_layout.addRow(self.working_folder, folder_selector)
        group.setLayout(folder_layout)
        self.layout.addWidget(group)

        # Initialize tab screen
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tabs.resize(300, 200)

        # Create tab
        program_element = ProgramStreamWidget(self.working_folder, parent.status_bar)
        tab_name = program_element.create_tab_program_layout()
        self.tab1.setLayout(program_element)
        self.tabs.addTab(self.tab1, tab_name)

        tab_layout, tab_name = self.create_tab_live_layout()
        self.tab2.setLayout(tab_layout)
        self.tabs.addTab(self.tab2, tab_name)

        # Add tabs to widget
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

    def set_folder_button(self):
        toolButtonOpenDialog = QtWidgets.QToolButton(self)
        toolButtonOpenDialog.setGeometry(QtCore.QRect(210, 10, 25, 19))
        toolButtonOpenDialog.setObjectName("FolderSelector")
        toolButtonOpenDialog.setText("...")
        toolButtonOpenDialog.clicked.connect(self._open_folder_dialog)
        return toolButtonOpenDialog

    def set_folder_edit(self):
        self.working_folder = QtWidgets.QLineEdit()
        self.working_folder.setEnabled(False)
        self.working_folder.setGeometry(QtCore.QRect(10, 10, 191, 20))
        self.working_folder.setObjectName("FolderName")
        self.working_folder.setFixedWidth(400)
        self.working_folder.setText(os.getcwd())
        return None

    def _open_folder_dialog(self):
        directory = str(QtWidgets.QFileDialog.getExistingDirectory())
        self.working_folder.setText('{}'.format(directory))

    def create_tab_live_layout(self):
        tab_layout = QtWidgets.QVBoxLayout(self)

        group = QtWidgets.QGroupBox("Channel to record:")
        layout = QtWidgets.QFormLayout()
        option = QtWidgets.QRadioButton("13")
        layout.addRow(option)
        option = QtWidgets.QRadioButton("Mega")
        layout.addRow(option)
        option = QtWidgets.QRadioButton("CHV")
        layout.addRow(option)
        option = QtWidgets.QRadioButton("TVN")
        layout.addRow(option)

        quality_label = QtWidgets.QLabel('Video quality:')
        self.live_quality = QtWidgets.QComboBox()
        layout.addRow(quality_label, self.live_quality)

        group.setLayout(layout)
        tab_layout.addWidget(group)

        tab_layout.addWidget(QtWidgets.QPushButton('Start Record Job'))

        return tab_layout, "Live TV Recorder"


class App(QtWidgets.QMainWindow):

    def __init__(self, app):
        super().__init__()
        self.title = 'TV Consumer'
        self.left = 0
        self.top = 0
        width, height = 500, 200
        self.select_app_style(app)
        self.setWindowTitle(self.title)
        self.resize(width, height)
        self.center()
        self.status_bar = self.statusBar()

        self.table_widget = MyTableWidget(self)
        self.setCentralWidget(self.table_widget)

        self.show()

    def select_app_style(self, app):
        if platform.system() == 'Windows':
            app.setStyle('WindowsVista')
        elif platform.system() == 'Darwin':
            app.setStyle('Macintosh')
        else:
            app.setStyle('Fusion')
        return None

    def center(self):
        # geometry of the main window
        qr = self.frameGeometry()
        # center point of screen
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        # move rectangle's center point to screen's center point
        qr.moveCenter(cp)
        # top left of rectangle becomes top left of window centering it
        self.move(qr.topLeft())

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = App(app)
    sys.exit(app.exec_())