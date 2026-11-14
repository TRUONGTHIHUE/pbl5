"""Optional real ZBar decode of a generated barcode image; NOT camera/YOLO validation."""
import io
import unittest

class SyntheticDecoderTest(unittest.TestCase):
    def test_ean13_keeps_leading_zero_with_real_zbar(self):
        try:
            from reportlab.graphics.barcode import createBarcodeDrawing
            from PIL import Image
            from pyzbar.pyzbar import decode
        except ImportError:
            self.skipTest('Optional ReportLab/Pillow/ZBar runtime unavailable')
        digits = '001234567890'
        check = str((-sum(int(d) * (1 if i % 2 == 0 else 3) for i,d in enumerate(digits))) % 10)
        try:
            drawing = createBarcodeDrawing('EAN13', value=digits, barHeight=70,
                                           barWidth=2, humanReadable=False)
            image = Image.open(io.BytesIO(drawing.asString('png'))).convert('RGB')
        except Exception:
            self.skipTest('Optional synthetic PNG renderer unavailable')
        values = {item.data.decode('utf-8') for item in decode(image)}
        self.assertIn(digits + check, values)
