"""
Generate QR Code for GitHub Repository
"""

import os

import qrcode

# Repository URL
REPO_URL = "https://github.com/iAmGiG/AutoTrader-AgentEdge"


def generate_qr_code():
    """Generate a high-resolution QR code for the repository."""

    # Create QR code with high error correction for print quality
    qr = qrcode.QRCode(
        version=1,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest error correction
        box_size=20,  # Large boxes for 300 DPI print
        border=4,  # Standard border
    )

    qr.add_data(REPO_URL)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to figures directory
    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "repo_qr_code.png")
    img.save(output_path)

    print("=" * 70)
    print("QR Code Generated Successfully!")
    print("=" * 70)
    print(f"Repository: {REPO_URL}")
    print(f"Saved to: {output_path}")
    print("Size: High resolution for printing")
    print()
    print("Usage: Add this to your poster so attendees can scan and access")
    print("       the repository directly from their phones!")
    print("=" * 70)


if __name__ == "__main__":
    generate_qr_code()
