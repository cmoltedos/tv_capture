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

class GenericStreamWidget(QtWidgets.QVBoxLayout):
    def __init__(self, folder, status_bar):
        super(GenericStreamWidget, self).__init__()
        self.stream = None
        self.quality = None
        self.working_folder = folder
        self.status_bar = status_bar

    def create_layout(self):
        group = QtWidgets.QGroupBox()
        layout = QtWidgets.QFormLayout()
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        layout.addRow(quality_label, self.quality)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start button', 'Stop button')

        return "Generic Class"

    def create_download_common_layout(self, start_name, stop_name):
        grid = QtWidgets.QGridLayout()
        self.start_download_button = QtWidgets.QPushButton(start_name)
        self.start_download_button.setEnabled(False)
        self.start_download_button.clicked.connect(
            self.start_stream_download)
        grid.addWidget(self.start_download_button, 1, 1)
        self.stop_download_button = QtWidgets.QPushButton(stop_name)
        self.stop_download_button.setEnabled(False)
        self.stop_download_button.clicked.connect(
            self.finish_stream_download)
        grid.addWidget(self.stop_download_button, 1, 2)
        self.addLayout(grid)

        self.pbar = QtWidgets.QProgressBar()
        self.pbar.setGeometry(30, 40, 200, 30)
        self.addWidget(self.pbar)
        return None

    def start_stream_download(self):
        self.start_download_button.setEnabled(False)
        self.stop_download_button.setEnabled(True)
        progress = self.stream.store_n_seconds(
            seconds=1, resolution=self.quality.currentText(),
            folder=self.working_folder.text()
        )
        self.progress = DownloadStreamProgress(progress)
        self.progress.percentChanged.connect(self.onpercentChanged)
        self.status_bar.showMessage('Downloading ...')
        self.progress.start()

    def finish_stream_download(self):
        self.progress.stop()
        self.start_download_button.setEnabled(True)
        self.stop_download_button.setEnabled(False)
        self.pbar.setValue(0)
        self.status_bar.showMessage('Finish')

    def onpercentChanged(self, value):
        if value >= 100:
            self.pbar.setValue(100)
            self.finish_stream_download()
        else:
            self.pbar.setValue(value)



class ProgramStreamWidget(GenericStreamWidget):

    def create_layout(self):
        group = QtWidgets.QGroupBox("Chapter to download URL:")
        layout = QtWidgets.QFormLayout()
        self.program_url = QtWidgets.QTextEdit()
        self.program_url.textChanged.connect(self.get_available_qualities)
        layout.addRow(self.program_url)
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        layout.addRow(quality_label, self.quality)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start Download', 'Stop Download')

        return "Program Downloader"

    def get_available_qualities(self):
        link = self.program_url.toPlainText()
        try:
            self.stream = streamer.Stream(link=link)
        except IOError:
            self.start_download_button.setEnabled(False)
            return None
        qualities = self.stream.get_available_resolution()
        self.quality.clear()
        self.quality.addItems(qualities)
        self.start_download_button.setEnabled(True)


class LiveStreamWidget(GenericStreamWidget):

    def create_layout(self):
        group = QtWidgets.QGroupBox("Chapter to download URL:")
        layout = QtWidgets.QFormLayout()
        self.program_url = QtWidgets.QTextEdit()
        self.program_url.textChanged.connect(self.get_available_qualities)
        layout.addRow(self.program_url)

        group = QtWidgets.QGroupBox("Channel to record:")
        options_layout = QtWidgets.QHBoxLayout()
        option = QtWidgets.QRadioButton("13")
        option.toggled.connect(lambda:self.get_available_qualities(option))
        options_layout.addWidget(option)
        option = QtWidgets.QRadioButton("Mega")
        option.toggled.connect(lambda:self.get_available_qualities(option))
        options_layout.addWidget(option)
        option = QtWidgets.QRadioButton("CHV")
        option.toggled.connect(lambda:self.get_available_qualities(option))
        options_layout.addWidget(option)
        option = QtWidgets.QRadioButton("TVN")
        option.toggled.connect(lambda:self.get_available_qualities(option))
        options_layout.addWidget(option)

        quality_layout = QtWidgets.QHBoxLayout()
        quality_label = QtWidgets.QLabel('Video quality:')
        self.quality = QtWidgets.QComboBox()
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality)
        quality_layout.addStretch(1)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(options_layout)
        layout.addLayout(quality_layout)
        group.setLayout(layout)
        self.addWidget(group)

        self.create_download_common_layout('Start Recording', 'Stop Recording')

        return "Live TV Recorder"

    def get_available_qualities(self, radio_button):
        if radio_button.isChecked():
            channel = radio_button.text().lower()
        else:
            channel = None
        try:
            self.stream = streamer.Stream(channel=channel)
        except IOError:
            self.start_download_button.setEnabled(False)
            return None
        qualities = self.stream.get_available_resolution()
        self.quality.clear()
        self.quality.addItems(qualities)
        self.start_download_button.setEnabled(True)



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
        tab_name = program_element.create_layout()
        self.tab1.setLayout(program_element)
        self.tabs.addTab(self.tab1, tab_name)

        live_element = LiveStreamWidget(self.working_folder, parent.status_bar)
        tab_name = live_element.create_layout()
        self.tab2.setLayout(live_element)
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