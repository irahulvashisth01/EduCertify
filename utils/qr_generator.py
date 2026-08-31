"""
QR code generation for certificate verification links.
"""

import os
import qrcode


def generate_qr_code(data: str, destination_folder: str, filename: str) -> str:
    """
    Generate a QR code PNG encoding `data` (the verification URL) and save
    it to destination_folder/filename. Returns the filename saved.
    """
    os.makedirs(destination_folder, exist_ok=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0b1f3a", back_color="white")
    full_path = os.path.join(destination_folder, filename)
    img.save(full_path)
    return filename
