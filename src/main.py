import json
import sys
import os
from PyQt6.QtGui import QPixmap
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QMenu, QPushButton, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QMimeData, QSize
from paddleocr import PaddleOCR
from PIL import Image
import cv2
import numpy as np
from sqlalchemy import false
import requests
import re
from utils.fileutils import format_file_size


class DragDropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("请拖拽图片文件到这里")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 2px dashed #aaa; font-size: 16px;")
        self.setAcceptDrops(True)
        self.parent_widget = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            local_path = url.toLocalFile()
            if local_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                self.parent_widget.add_image_file(local_path)
        event.acceptProposedAction()



class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片拖拽识别演示 - PaddleOCR")
        self.resize(800, 400)

        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False)

        self.files = []  # 存放文件路径

        # 主体横向布局
        h_layout = QHBoxLayout(self)

        # 左边拖拽区
        self.drag_label = DragDropLabel(self)
        h_layout.addWidget(self.drag_label, 1)

        # 右侧：列表 + 按钮 + 文本
        right_layout = QVBoxLayout()

        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.open_menu)
        right_layout.addWidget(self.list_widget)

        # 清空按钮（靠左，小尺寸）
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self.clear_list)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # 新增：格式化数据按钮
        format_btn = QPushButton("格式化数据")
        format_btn.clicked.connect(self.format_text_edit_content)
        format_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 新增：核验票据按钮（占位）
        verify_btn = QPushButton("核验票据")
        verify_btn.clicked.connect(self.verify_invoice)
        verify_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(format_btn)
        btn_layout.addWidget(verify_btn)
        btn_layout.addStretch()  # 让按钮靠左

        right_layout.addLayout(btn_layout)

        # 文本显示控件（识别结果）
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("这里显示识别结果文本，可复制...")
        self.text_edit.setFixedHeight(150)  # 固定高度，可根据需要调整
        right_layout.addWidget(self.text_edit)

        # 添加右侧布局
        h_layout.addLayout(right_layout, 3)


    def add_image_file(self, filepath):
        if filepath not in self.files:
            self.files.append(filepath)

            # 构造缩略图
            thumb = QPixmap(filepath).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


        # 构造 item 展示文本
            file_name = os.path.basename(filepath)
            file_size = format_file_size(os.path.getsize(filepath))

            text = f"{file_name}\n路径: {filepath}\n大小: {file_size}"
            item = QListWidgetItem(QIcon(thumb), text)
            item.setData(Qt.ItemDataRole.UserRole, filepath)

            self.list_widget.addItem(item)

    def open_menu(self, position):
        item = self.list_widget.itemAt(position)
        if item is None:
            return

        menu = QMenu()
        recognize_action = menu.addAction("识别")
        delete_action = menu.addAction("删除")
        action = menu.exec(self.list_widget.mapToGlobal(position))

        if action == recognize_action:
            self.recognize_image(item.data(Qt.ItemDataRole.UserRole))
        elif action == delete_action:
            row = self.list_widget.row(item)
            filepath = item.data(Qt.ItemDataRole.UserRole)
            self.files.remove(filepath)
            self.list_widget.takeItem(row)


    def clear_list(self):
        self.files.clear()
        self.list_widget.clear()

    def recognize_image(self, filepath):
        try:
            # 解决中文路径加载失败问题
            image = Image.open(filepath)  # 中文路径OK
            image_np = np.array(image)
            # 对示例图像执行 OCR 推理
            result=self.ocr.ocr(image_np)
            # 存储的图片和json文件路径
            filename_without_ext = os.path.splitext(os.path.basename(filepath))[0]
            save_img_path = "output/" + filename_without_ext + ".png"
            save_json_path = "output/" + filename_without_ext + ".json"
            # 可视化结果并保存 json 结果
            for res in result:
                res.print()
                res.save_to_img(save_path=save_img_path)
                res.save_to_json(save_path=save_json_path)

            # 显示识别结果
            with open(save_json_path, "r", encoding="utf-8") as f:
                content = f.read()
                data = json.loads(content)  # 解析成Python对象（字典等）
                rec_texts = data.get("rec_texts", [])  # 取出rec_texts列表，默认空列表
                # 拼接成一段文本，用换行符连接
                text_to_show = "\n".join(rec_texts)
                self.text_edit.setPlainText(text_to_show)

        except Exception as e:
            print( "错误", f"识别失败：{e}")
            QMessageBox.warning(self, "错误", f"识别失败：{e}")


    # deepseek-chat 的模型调用
    # def format_text_edit_content(self):
    #     # 请求地址
    #     url = "https://api.deepseek.com/chat/completions"
    #     # 请求头
    #     headers = {
    #         "Authorization": "Bearer sk-e99fc0af3461439395a7a1507d1cde1b",
    #         "Content-Type": "application/json"
    #     }
    #     # 构建 content 文本
    #     prompt = (
    #         "格式化下面信息，以下面格式发我：\n"
    #         "{\n"
    #         '  "InvoiceNo": "25347000000854698562",\n'
    #         '  "InvoiceDate": "2021-07-11",\n'
    #         '  "Amount": "12.45"\n'
    #         "}\n\n"
    #         "InvoiceNo表示发票号码，InvoiceDate表示开票日期，Amount表示合计金额。\n\n"
    #     )
    #     # 加上 text_edit 中的内容
    #     full_content = prompt + self.text_edit.toPlainText()
    #     # 请求体参数
    #     payload = {
    #         "messages": [
    #             {
    #                 "role": "system",
    #                 "content": full_content
    #             }
    #         ],
    #         "model": "deepseek-chat",
    #         "frequency_penalty": 0,
    #         "max_tokens": 2048,
    #         "presence_penalty": 0,
    #         "response_format": {
    #             "type": "text"
    #         },
    #         "stop": None,
    #         "stream": False,
    #         "stream_options": None,
    #         "temperature": 1,
    #         "top_p": 1,
    #         "tools": None,
    #         "tool_choice": "none",
    #         "logprobs": False,
    #         "top_logprobs": None
    #     }
    #     print("请求内容:", payload)
    #     # 发起 POST 请求
    #     response = requests.post(url, headers=headers, json=payload)
    #
    #     # 输出响应结果
    #     print("状态码:", response.status_code)
    #     try:
    #         print("响应内容:", response.text)
    #         data = json.loads(response.text)
    #         # 获取 content 内容
    #         content = data['choices'][0]['message']['content']
    #         print("content的信息"+content)
    #         # 去除 ```json ``` 标签
    #         json_str = re.sub(r'^```json\n|\n```$', '', content.strip())
    #         print("去除 ```json ``` 标签:", json_str)
    #         # 转成字典
    #         self.text_edit.setPlainText(json_str)
    #
    #     except Exception:
    #         self.text_edit.setPlainText(response.text)
    #         print("响应内容非 JSON:", response.text)

    # 豆包的模型调用
    def format_text_edit_content(self):

        # 请求地址
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        # 请求头
        headers = {
            "Authorization": "Bearer 746a3207-6de6-4fd3-be02-c4c6fe7bf6eb",
            "Content-Type": "application/json"
        }
        # 构建 content 文本
        prompt = (
            "格式化下面信息，以下面格式发我：\n"
            "{\n"
            '  "InvoiceNo": "25347000000854698562",\n'
            '  "InvoiceDate": "2021-07-11",\n'
            '  "Amount": "12.45"\n'
            "}\n\n"
            "InvoiceNo表示发票号码，InvoiceDate表示开票日期，Amount表示合计金额。\n\n"
        )
        # 加上 text_edit 中的内容
        full_content = prompt + self.text_edit.toPlainText()
        # 请求体参数
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": full_content
                }
            ],
            "model": "doubao-seed-1.6-250615",
            "thinking":{
                "type":"disabled"
            }
        }
        print("请求内容:", payload)
        # 发起 POST 请求
        response = requests.post(url, headers=headers, json=payload)

        # 输出响应结果
        print("状态码:", response.status_code)
        try:
            print("响应内容:", response.text)
            data = json.loads(response.text)
            # 获取 content 内容
            content = data['choices'][0]['message']['content']
            print("content的信息"+content)
            # 转成字典
            self.text_edit.setPlainText(content)

        except Exception:
            self.text_edit.setPlainText(response.text)
            print("响应内容非 JSON:", response.text)

    def verify_invoice(self):
        # 暂未实现功能，可扩展接入发票查验接口
        QMessageBox.information(self, "提示", "核验票据功能暂未实现。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
