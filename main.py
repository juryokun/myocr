import sys
import tempfile
from datetime import datetime
from pathlib import Path

from paddleocr import PaddleOCR
from PIL import Image, ImageEnhance, ImageGrab, ImageOps
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class OCRWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OCRツール")
        self.resize(800, 600)

        self.ocr = PaddleOCR(
            lang="japan",
            use_angle_cls=False,
        )

        self.image_files = []
        self.output_dir = Path.cwd() / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.output_file = None

        self.create_ui()

    def create_ui(self):
        self.label = QLabel("画像未選択")

        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(False)

        self.btn_file = QPushButton("画像選択")
        self.btn_dir = QPushButton("ディレクトリ選択")
        self.btn_clip = QPushButton("クリップボード貼り付け")
        self.btn_run = QPushButton("OCR実行")
        self.btn_copy = QPushButton("結果をコピー")
        self.btn_save = QPushButton("修正内容を保存")

        self.rb_new = QRadioButton("新規ファイル")
        self.rb_append = QRadioButton("前回ファイルへ追記")
        self.rb_new.setChecked(True)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.rb_new)
        radio_layout.addWidget(self.rb_append)

        run_layout = QHBoxLayout()
        run_layout.addWidget(self.btn_run)
        run_layout.addWidget(self.btn_copy)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_file)
        button_layout.addWidget(self.btn_dir)
        button_layout.addWidget(self.btn_clip)
        button_layout.addWidget(self.btn_save)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addLayout(button_layout)
        layout.addLayout(radio_layout)
        layout.addWidget(self.result_edit)
        layout.addLayout(run_layout)

        self.setLayout(layout)

        self.btn_file.clicked.connect(self.select_files)
        self.btn_dir.clicked.connect(self.select_directory)
        self.btn_clip.clicked.connect(self.paste_image)
        self.btn_run.clicked.connect(self.run_ocr)
        self.btn_copy.clicked.connect(self.copy_result)
        self.btn_save.clicked.connect(self.save_edited_text)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "画像選択", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )

        if files:
            self.image_files = files
            self.label.setText(f"{len(files)}件選択")

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダ選択")

        if not folder:
            return

        path = Path(folder)

        self.image_files = []

        for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"):
            self.image_files.extend(path.glob(ext))

        self.image_files = sorted([str(f) for f in self.image_files])

        self.label.setText(f"{len(self.image_files)}件検出")

    def paste_image(self):
        image = ImageGrab.grabclipboard()

        if image is None:
            QMessageBox.warning(self, "エラー", "クリップボードに画像がありません")
            return

        image_dir = Path.cwd() / "images"
        image_dir.mkdir(exist_ok=True)

        filename = datetime.now().strftime("%Y%m%d_%H%M%S.png")

        image_path = image_dir / filename
        image.save(image_path)

        self.image_files = [str(image_path)]
        self.label.setText(f"貼り付け画像: {filename}")

    def run_ocr(self):
        if not self.image_files:
            QMessageBox.warning(self, "エラー", "画像を選択してください")
            return

        all_text = []

        for file in self.image_files:
            self.result_edit.append(f"処理中: {Path(file).name}")

            result = self.ocr.ocr(file, cls=False)

            texts = []

            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    score = line[1][1]

                    text = text.strip()

                    if (
                        texts
                        and not texts[-1].endswith(("。", "！", "？"))
                        and len(text) <= 5
                    ):
                        texts[-1] += text
                    else:
                        texts.append(text)

            text = "\n".join(texts)

            all_text.append(f"----- {Path(file).name} -----\n{text}\n")

        output_text = "\n".join(all_text)

        self.result_edit.clear()
        self.result_edit.setPlainText(output_text)

        self.save_text(output_text)

    def save_text(self, text):
        if self.rb_new.isChecked():
            filename = datetime.now().strftime("%Y%m%d_%H%M%S.txt")
            self.output_file = self.output_dir / filename
            mode = "w"
        else:
            self.output_file = self.output_dir / "ocr_result.txt"
            mode = "a"

        with open(self.output_file, mode, encoding="utf-8") as f:
            f.write(text)
            f.write("\n")

        QMessageBox.information(self, "完了", f"保存しました\n{self.output_file}")

    def save_edited_text(self):
        if self.output_file is None:
            QMessageBox.warning(self, "エラー", "保存先ファイルがありません")
            return

        text = self.result_edit.toPlainText()

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(text)

        QMessageBox.information(
            self, "完了", f"修正内容を保存しました\n{self.output_file}"
        )

    def preprocess_image(self, image_path):
        img = Image.open(image_path)

        # 2倍に拡大
        img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)

        # コントラスト強調
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # グレースケール
        gray = ImageOps.grayscale(img)

        # 二値化
        bw = gray.point(lambda x: 255 if x > 120 else 0, mode="1")

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)

        bw.save(tmp.name)

        return tmp.name

    def copy_result(self):
        text = self.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = OCRWindow()
    window.show()

    sys.exit(app.exec())
