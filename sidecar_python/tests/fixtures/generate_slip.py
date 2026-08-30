"""
Utility script to generate a high-fidelity synthetic container gate slip image for testing and demos.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def generate_sample_slip(output_path: str = "sample_container_slip.jpg"):
    # Create high-res white background document
    width, height = 1200, 900
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(40, 60, 90), width=3)
    draw.rectangle([(35, 35), (width - 35, height - 35)], outline=(180, 195, 215), width=1)

    # Header Banner
    draw.rectangle([(40, 40), (width - 40, 130)], fill=(24, 43, 73))
    draw.text((60, 55), "GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT", fill=(255, 255, 255))
    draw.text((60, 90), "GATE-IN VERIFICATION & VERIFIED GROSS MASS (VGM) CERTIFICATE", fill=(180, 210, 245))

    # Grid Boxes
    # Box 1: Container Identification
    draw.rectangle([(50, 150), (width - 50, 280)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 165), "CONTAINER IDENTIFICATION", fill=(24, 43, 73))
    draw.text((70, 200), "CONTAINER NO:", fill=(80, 90, 110))
    draw.text((220, 195), "MSCU 492019 5", fill=(0, 0, 0))
    draw.text((550, 200), "TYPE / ISO CODE:", fill=(80, 90, 110))
    draw.text((730, 195), "40HC (45G1)", fill=(0, 0, 0))
    draw.text((70, 240), "DIMENSIONS:", fill=(80, 90, 110))
    draw.text((220, 238), "40' x 8' x 9'6\" (12.19m x 2.44m x 2.89m)", fill=(0, 0, 0))

    # Box 2: Weights Breakdown
    draw.rectangle([(50, 300), (width - 50, 440)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 315), "WEIGHT & CARGO MEASUREMENTS", fill=(24, 43, 73))
    draw.text((70, 350), "TARE WEIGHT:", fill=(80, 90, 110))
    draw.text((240, 348), "3,800 KG  /  8,377 LBS", fill=(0, 0, 0))
    draw.text((550, 350), "NET CARGO WT:", fill=(80, 90, 110))
    draw.text((730, 348), "22,400 KG", fill=(0, 0, 0))
    draw.text((70, 395), "VERIFIED GROSS MASS (VGM):", fill=(180, 30, 30))
    draw.text((350, 392), "26,200 KG  [VERIFIED ACCURATE]", fill=(180, 30, 30))

    # Box 3: Commodity and Hazardous Cargo
    draw.rectangle([(50, 460), (width - 50, 600)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 475), "CARGO MANIFEST & DANGEROUS GOODS CLASSIFICATION", fill=(24, 43, 73))
    draw.text((70, 510), "COMMODITY DESC:", fill=(80, 90, 110))
    draw.text((240, 508), "ELECTRONIC COMPONENTS & LITHIUM CELLS", fill=(0, 0, 0))
    draw.text((70, 555), "HAZMAT STATUS:", fill=(80, 90, 110))
    draw.text((240, 552), "HAZARDOUS - UN 3480 CLASS 9 (LITHIUM ION BATTERIES)", fill=(180, 30, 30))

    # Box 4: Routing & Destination
    draw.rectangle([(50, 620), (width - 50, 750)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 635), "VOYAGE & DISCHARGE ROUTING", fill=(24, 43, 73))
    draw.text((70, 670), "PORT OF DISCHARGE:", fill=(80, 90, 110))
    draw.text((260, 668), "PORT OF SINGAPORE (SGSIN)", fill=(0, 0, 0))
    draw.text((550, 670), "SEAL NUMBER:", fill=(80, 90, 110))
    draw.text((730, 668), "ML-SG-987214", fill=(0, 0, 0))
    draw.text((70, 710), "CARRIER / OPERATOR:", fill=(80, 90, 110))
    draw.text((260, 708), "MEDITERRANEAN SHIPPING COMPANY", fill=(0, 0, 0))

    # Stamp Overlay
    draw.rectangle([(width - 320, height - 120), (width - 60, height - 50)], outline=(30, 140, 60), width=2)
    draw.text((width - 300, height - 100), "APPROVED FOR LOADING", fill=(30, 140, 60))
    draw.text((width - 300, height - 75), "PORT AUTHORITY GATE 04", fill=(30, 140, 60))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Sample slip generated at: {output_path}")


def generate_heavy_slip(output_path: str = "sidecar_python/tests/fixtures/heavy_container_slip.jpg"):
    width, height = 1200, 900
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(40, 60, 90), width=3)
    draw.rectangle([(35, 35), (width - 35, height - 35)], outline=(180, 195, 215), width=1)

    draw.rectangle([(40, 40), (width - 40, 130)], fill=(24, 43, 73))
    draw.text((60, 55), "GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT", fill=(255, 255, 255))
    draw.text((60, 90), "GATE-IN VERIFICATION & VERIFIED GROSS MASS (VGM) CERTIFICATE", fill=(180, 210, 245))

    # Box 1: Container Identification
    draw.rectangle([(50, 150), (width - 50, 280)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 165), "CONTAINER IDENTIFICATION", fill=(24, 43, 73))
    draw.text((70, 200), "CONTAINER NO:", fill=(80, 90, 110))
    draw.text((220, 195), "MSCU 889201 3", fill=(0, 0, 0))
    draw.text((550, 200), "TYPE / ISO CODE:", fill=(80, 90, 110))
    draw.text((730, 195), "20GP (22G1)", fill=(0, 0, 0))
    draw.text((70, 240), "DIMENSIONS:", fill=(80, 90, 110))
    draw.text((220, 238), "20' x 8' x 8'6\" (6.06m x 2.44m x 2.59m)", fill=(0, 0, 0))

    # Box 2: Weights Breakdown
    draw.rectangle([(50, 300), (width - 50, 440)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 315), "WEIGHT & CARGO MEASUREMENTS", fill=(24, 43, 73))
    draw.text((70, 350), "TARE WEIGHT:", fill=(80, 90, 110))
    draw.text((240, 348), "2,300 KG  /  5,070 LBS", fill=(0, 0, 0))
    draw.text((550, 350), "NET CARGO WT:", fill=(80, 90, 110))
    draw.text((730, 348), "32,200 KG", fill=(0, 0, 0))
    draw.text((70, 395), "VERIFIED GROSS MASS (VGM):", fill=(180, 30, 30))
    draw.text((350, 392), "34,500 KG  [VERIFIED ACCURATE]", fill=(180, 30, 30))

    # Box 3: Commodity and Cargo
    draw.rectangle([(50, 460), (width - 50, 600)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 475), "CARGO MANIFEST & CLASSIFICATION", fill=(24, 43, 73))
    draw.text((70, 510), "COMMODITY DESC:", fill=(80, 90, 110))
    draw.text((240, 508), "MACHINERY PARTS & STEEL FORGINGS", fill=(0, 0, 0))
    draw.text((70, 555), "HAZMAT STATUS:", fill=(80, 90, 110))
    draw.text((240, 552), "NON-HAZARDOUS GENERAL CARGO", fill=(0, 120, 0))

    # Box 4: Routing & Destination
    draw.rectangle([(50, 620), (width - 50, 750)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 635), "VOYAGE & DISCHARGE ROUTING", fill=(24, 43, 73))
    draw.text((70, 670), "PORT OF DISCHARGE:", fill=(80, 90, 110))
    draw.text((260, 668), "PORT OF ROTTERDAM (NLRTM)", fill=(0, 0, 0))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Heavy slip generated at: {output_path}")


def generate_inconsistent_weight_slip(output_path: str = "sidecar_python/tests/fixtures/inconsistent_weight_slip.jpg"):
    width, height = 1200, 900
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(40, 60, 90), width=3)
    draw.rectangle([(35, 35), (width - 35, height - 35)], outline=(180, 195, 215), width=1)

    draw.rectangle([(40, 40), (width - 40, 130)], fill=(24, 43, 73))
    draw.text((60, 55), "GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT", fill=(255, 255, 255))
    draw.text((60, 90), "GATE-IN VERIFICATION & VERIFIED GROSS MASS (VGM) CERTIFICATE", fill=(180, 210, 245))

    draw.rectangle([(50, 150), (width - 50, 280)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 165), "CONTAINER IDENTIFICATION", fill=(24, 43, 73))
    draw.text((70, 200), "CONTAINER NO:", fill=(80, 90, 110))
    draw.text((220, 195), "CMAU 555123 4", fill=(0, 0, 0))
    draw.text((550, 200), "TYPE / ISO CODE:", fill=(80, 90, 110))
    draw.text((730, 195), "40HC (45G1)", fill=(0, 0, 0))

    draw.rectangle([(50, 300), (width - 50, 440)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 315), "WEIGHT & CARGO MEASUREMENTS", fill=(24, 43, 73))
    draw.text((70, 350), "TARE WEIGHT:", fill=(80, 90, 110))
    draw.text((240, 348), "3,800 KG  /  8,377 LBS", fill=(0, 0, 0))
    draw.text((550, 350), "NET CARGO WT:", fill=(80, 90, 110))
    draw.text((730, 348), "10,000 KG", fill=(0, 0, 0))
    # Inconsistent: 3,800 + 10,000 = 13,800, but Gross claims 28,000 KG (Discrepancy > 14,000 KG!)
    draw.text((70, 395), "VERIFIED GROSS MASS (VGM):", fill=(180, 30, 30))
    draw.text((350, 392), "28,000 KG  [VERIFIED ACCURATE]", fill=(180, 30, 30))

    draw.rectangle([(50, 460), (width - 50, 600)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 475), "CARGO MANIFEST", fill=(24, 43, 73))
    draw.text((70, 510), "COMMODITY DESC:", fill=(80, 90, 110))
    draw.text((240, 508), "INCONSISTENT GENERAL CARGO", fill=(0, 0, 0))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Inconsistent slip generated at: {output_path}")


def generate_degraded_slip(output_path: str = "sidecar_python/tests/fixtures/low_confidence_slip.jpg"):
    import random
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=(140, 140, 140))
    draw = ImageDraw.Draw(img)

    # Low contrast blurry text with noise
    for _ in range(5000):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(90, 170), random.randint(90, 170), random.randint(90, 170)))

    draw.text((50, 80), "C 0 N T A 1 N E R   R E C E I P T ???", fill=(120, 120, 120))
    draw.text((50, 150), "NO: X X X 9 9 ~ ~ ~", fill=(110, 110, 110))
    draw.text((50, 220), "WT: ~ ~ ~ KG", fill=(115, 115, 115))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=40)
    print(f"Degraded slip generated at: {output_path}")


def generate_blurred_slip(output_path: str = "sidecar_python/tests/fixtures/blurred_container_slip.jpg"):
    from PIL import ImageFilter
    fixtures_dir = os.path.dirname(os.path.abspath(output_path))
    sample_path = os.path.join(fixtures_dir, "sample_container_slip.jpg")
    if not os.path.exists(sample_path):
        generate_sample_slip(sample_path)
    img = Image.open(sample_path)
    # Apply severe Gaussian blur
    blurred = img.filter(ImageFilter.GaussianBlur(radius=8.0))
    blurred.save(output_path, quality=90)
    print(f"Blurred slip generated at: {output_path}")


def generate_rotated_slip(output_path: str = "sidecar_python/tests/fixtures/rotated_container_slip.jpg"):
    fixtures_dir = os.path.dirname(os.path.abspath(output_path))
    sample_path = os.path.join(fixtures_dir, "sample_container_slip.jpg")
    if not os.path.exists(sample_path):
        generate_sample_slip(sample_path)
    img = Image.open(sample_path)
    # Rotate 35 degrees with expansion
    rotated = img.rotate(35, expand=True, fillcolor=(250, 250, 252))
    rotated.save(output_path, quality=95)
    print(f"Rotated slip generated at: {output_path}")


def generate_missing_weight_slip(output_path: str = "sidecar_python/tests/fixtures/missing_weight_slip.jpg"):
    width, height = 1200, 900
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(40, 60, 90), width=3)
    draw.rectangle([(40, 40), (width - 40, 130)], fill=(24, 43, 73))
    draw.text((60, 55), "GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT", fill=(255, 255, 255))
    draw.text((60, 90), "GATE-IN UNWEIGHTED MANIFEST", fill=(180, 210, 245))

    draw.rectangle([(50, 150), (width - 50, 280)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 200), "CONTAINER NO:", fill=(80, 90, 110))
    draw.text((220, 195), "MSCU 123456 7", fill=(0, 0, 0))
    draw.text((550, 200), "TYPE / ISO CODE:", fill=(80, 90, 110))
    draw.text((730, 195), "40HC (45G1)", fill=(0, 0, 0))

    # Missing weights box (empty or pending)
    draw.rectangle([(50, 300), (width - 50, 440)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 315), "WEIGHT & CARGO MEASUREMENTS", fill=(24, 43, 73))
    draw.text((70, 350), "WEIGHT STATUS:", fill=(180, 30, 30))
    draw.text((240, 348), "WEIGHING PENDING - NO VGM RECORDED", fill=(180, 30, 30))

    draw.rectangle([(50, 460), (width - 50, 600)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 510), "COMMODITY DESC:", fill=(80, 90, 110))
    draw.text((240, 508), "GENERAL DRY FREIGHT", fill=(0, 0, 0))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Missing weight slip generated at: {output_path}")


def generate_invalid_container_num_slip(output_path: str = "sidecar_python/tests/fixtures/invalid_container_num_slip.jpg"):
    width, height = 1200, 900
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(40, 60, 90), width=3)
    draw.rectangle([(40, 40), (width - 40, 130)], fill=(24, 43, 73))
    draw.text((60, 55), "GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT", fill=(255, 255, 255))

    draw.rectangle([(50, 150), (width - 50, 280)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 200), "CONTAINER NO:", fill=(80, 90, 110))
    # Invalid check digit (MSCU 492019 9 is invalid, correct is 5)
    draw.text((220, 195), "MSCU 492019 9", fill=(0, 0, 0))
    draw.text((550, 200), "TYPE / ISO CODE:", fill=(80, 90, 110))
    draw.text((730, 195), "40HC (45G1)", fill=(0, 0, 0))

    draw.rectangle([(50, 300), (width - 50, 440)], fill=(240, 244, 250), outline=(160, 180, 210), width=2)
    draw.text((70, 350), "TARE WEIGHT:", fill=(80, 90, 110))
    draw.text((240, 348), "3,800 KG", fill=(0, 0, 0))
    draw.text((550, 350), "NET CARGO WT:", fill=(80, 90, 110))
    draw.text((730, 348), "18,000 KG", fill=(0, 0, 0))
    draw.text((70, 395), "VERIFIED GROSS MASS (VGM):", fill=(180, 30, 30))
    draw.text((350, 392), "21,800 KG  [VERIFIED ACCURATE]", fill=(180, 30, 30))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Invalid container num slip generated at: {output_path}")


if __name__ == "__main__":
    fixtures_dir = os.path.dirname(os.path.abspath(__file__))
    generate_sample_slip(os.path.join(fixtures_dir, "sample_container_slip.jpg"))
    generate_heavy_slip(os.path.join(fixtures_dir, "heavy_container_slip.jpg"))
    generate_inconsistent_weight_slip(os.path.join(fixtures_dir, "inconsistent_weight_slip.jpg"))
    generate_degraded_slip(os.path.join(fixtures_dir, "low_confidence_slip.jpg"))
    generate_blurred_slip(os.path.join(fixtures_dir, "blurred_container_slip.jpg"))
    generate_rotated_slip(os.path.join(fixtures_dir, "rotated_container_slip.jpg"))
    generate_missing_weight_slip(os.path.join(fixtures_dir, "missing_weight_slip.jpg"))
    generate_invalid_container_num_slip(os.path.join(fixtures_dir, "invalid_container_num_slip.jpg"))


