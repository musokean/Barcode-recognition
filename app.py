from flask import Flask, request, jsonify, send_file, render_template
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance, ImageFilter
import os
import uuid
import xlwt
from datetime import datetime

app = Flask(__name__)

# 配置文件夹路径
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
RESULTS_FOLDER = os.path.join(os.getcwd(), 'static/results')

# 确保文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')  # 渲染前端页面

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # 检查文件格式
        allowed_extensions = {'.jpg', '.png', '.bmp', '.tiff'}
        ext = os.path.splitext(file.filename)[-1].lower()
        if ext not in allowed_extensions:
            return jsonify({'error': f'Unsupported file format: {ext}'}), 400

        # 保存上传文件
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)

        # 返回成功消息和文件路径
        return jsonify({'message': 'File uploaded successfully', 'filename': unique_filename})
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/decode', methods=['POST'])
def decode_barcodes():
    try:
        data = request.json
        if 'filename' not in data:
            return jsonify({'error': 'No file specified'}), 400

        file_path = os.path.join(UPLOAD_FOLDER, data['filename'])
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        all_barcodes = []

        # 第一阶段：图像预处理 - 灰度化和对比度增强
        image = Image.open(file_path)
        grayscale_image = image.convert('L')
        contrast_enhancer = ImageEnhance.Contrast(grayscale_image)
        contrast_image = contrast_enhancer.enhance(0.3)

        # 解码第一阶段结果
        decoded_objects = decode(contrast_image)
        barcodes = [{'content': obj.data.decode('utf-8'), 'type': obj.type} for obj in decoded_objects]
        all_barcodes.extend(barcodes)

        # 第二阶段：进一步预处理 - 高斯模糊
        blurred_image = contrast_image.filter(ImageFilter.GaussianBlur(2))

        # 解码第二阶段结果
        decoded_objects = decode(blurred_image)
        barcodes = [{'content': obj.data.decode('utf-8'), 'type': obj.type} for obj in decoded_objects]
        all_barcodes.extend(barcodes)

        # 第三阶段：进一步预处理 - 边缘增强
        edge_enhanced_image = blurred_image.filter(ImageFilter.EDGE_ENHANCE)

        # 解码第三阶段结果
        decoded_objects = decode(edge_enhanced_image)
        barcodes = [{'content': obj.data.decode('utf-8'), 'type': obj.type} for obj in decoded_objects]
        all_barcodes.extend(barcodes)

        # 去重
        all_barcodes = list({barcode['content']: barcode for barcode in all_barcodes}.values())

        # 保存到唯一的 Excel 文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"results_{timestamp}.xls"
        excel_path = os.path.join(RESULTS_FOLDER, excel_filename)

        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Barcodes')
        sheet.write(0, 0, 'Barcode Content')
        sheet.write(0, 1, 'Type')

        for idx, barcode in enumerate(all_barcodes, start=1):
            sheet.write(idx, 0, barcode['content'])
            sheet.write(idx, 1, barcode['type'])

        workbook.save(excel_path)

        # 返回每一步处理的图片路径
        return jsonify({
            'barcodes': all_barcodes,
            'download_url': f'/download/{excel_filename}'
        })

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(RESULTS_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=3000, debug=True)
